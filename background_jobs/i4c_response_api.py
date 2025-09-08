from datetime import datetime
import os
import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import json
from utils.aes_encryption_decryption import AESUtil
import requests

from utils.db_connection import db

def call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, received_dt, log_file_name):
    logger = logging.getLogger(log_file_name)
    logger.info('')
    aes_util = AESUtil()
    encrypted_i4c_payload = aes_util.aes_encrypt(kvb_key, json.dumps(i4c_payload))
    src_channel = os.getenv("KVB_SRC_CHANNEL", "")
    username = os.getenv("KVB_USERNAME", "")
    password = os.getenv("KVB_PASSWORD", "")
    i4c_post_payload = {
        "in_msg": {
            "Src_Channel": src_channel,
            "UserName": username,
            "Password": password,
            "encryptReq": encrypted_i4c_payload
        }
    }
    env_i4c_response_path = os.getenv("I4C_RESPONSE_PATH", "/ESB/CyberCrimeI4CRes")
    i4c_response_url = kvb_endpoint.rstrip("/") + "/" + env_i4c_response_path.lstrip("/")
    logger.info(f"[I4C_RESPONSE_API_REQUEST] {json.dumps(i4c_post_payload)}")
    successful_response = False
    try:
        i4c_resp = requests.post(i4c_response_url, json=i4c_post_payload, timeout=30)
        logger.info(f"[I4C_RESPONSE_API_RESPONSE] {i4c_resp.status_code} {i4c_resp.text}")
        i4c_resp_json = i4c_resp.json()
        i4c_encrypt_res = i4c_resp_json.get("out_msg", {}).get("encryptRes")
        if i4c_encrypt_res:
            decrypted_i4c = aes_util.aes_decrypt(kvb_key, i4c_encrypt_res)
            logger.info(f"[I4C_RESPONSE_DECRYPTED_RESPONSE] {decrypted_i4c}")
            try:
                decrypted_obj = json.loads(decrypted_i4c)
                statuscode = decrypted_obj.get('statuscode')
                status_message = decrypted_obj.get('status_message')
                if str(statuscode) == "200" and str(status_message).lower() == "success":
                    successful_response = True
                    logger.info(f"[I4C_RESPONSE_SUCCESS] {json.dumps(decrypted_obj, indent=4)}")
                else:
                    logger.error(f"[I4C_RESPONSE_ERROR] {json.dumps(decrypted_obj, indent=4)}")
            except Exception as dec_exc:
                logger.error(f"[I4C_RESPONSE_DECODE_ERROR] {dec_exc}")
            db.create_record_(
                response_table,
                {
                    'job_id': i4c_payload['job_id'],
                    'ack_no': i4c_payload['acknowledgement_no'],
                    'rrn': i4c_payload['transactions'][0].get('rrn_transaction_id', '') or i4c_payload['transactions'][0].get('root_rrn_transaction_id', ''),
                    'incident_response': decrypted_i4c,
                    'received_dt': received_dt,
                    'is_success': successful_response
                }
            )
        else:
            logger.error("[I4C_RESPONSE_ERROR] No encrypted response found in I4C response")
    except Exception as i4c_exc:
        logger.error(f"[I4C_RESPONSE_API_ERROR] {i4c_exc}")

    return successful_response

def send_invalid_rrn_response(
    status_code: str,
    data: dict,
    incident: dict,
    decrypted_obj: dict,
    rrn: str,
    phone_number: str,
    email: str,
    kvb_key: str,
    kvb_endpoint: str,
    response_table: str,
    log_file_name: str,
    db,
    incidents_table: str
):
    
    """
    Helper function to send invalid RRN response (status codes 01, 02, 99).
    """
    payload_data = data.get("request", {})
    acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
    job_id = str(data.get("job_id", ""))
    instrument_data = payload_data.get("instrument", {})
    payer_account_number = str(instrument_data.get("payer_account_number", ""))

    # Get additional fields from CASA response (same as hold API)
    pan_number = (decrypted_obj.get("PAN", "") if decrypted_obj else "") or "FORM60"
    ifsc_code = decrypted_obj.get("IFSCCode", "") if decrypted_obj else ""
    net_balance = decrypted_obj.get("NetBalance", None) if decrypted_obj else None
    disputed_amount = incident.get("disputed_amount", 0)
    disputed_amount_float = float(disputed_amount) if disputed_amount else 0.0
    amount = incident.get("amount", 0)
    amount_float = float(amount) if amount else 0.0

    # Use current timestamp for invalid RRN
    current_timestamp = datetime.now()
    transaction_datetime_val = current_timestamp.strftime("%Y-%m-%d %H:%M:%S")
    amount_str = "{:.2f}".format(amount_float)
    disputed_amount_str = "{:.2f}".format(disputed_amount_float)

    # Build the invalid payload
    invalid_rrn_payload = {
        "acknowledgement_no": acknowledgement_no,
        "job_id": job_id,
        "transactions": [
            {
                "amount": amount_str,
                "transaction_datetime": transaction_datetime_val,
                "disputed_amount": disputed_amount_str,
                "phone_number": phone_number,
                "email": email,
                "pan_number": pan_number,
                "ifsc_code": ifsc_code,
                "root_account_number": payer_account_number,
                "root_rrn_transaction_id": rrn,
                "root_bankid": "25",
                "status_code": status_code,
                "root_effective_balance": str(net_balance) if net_balance is not None else "",
                "root_ifsc_code": ifsc_code,
                "remarks": acknowledgement_no,
            }
        ]
    }

    logger = logging.getLogger(log_file_name)
    logger.info(f"[RRN_VALIDATION] Preparing to send status code {status_code} response for RRN: {rrn}")
    logger.info(f"[RRN_VALIDATION][INVALID_RRN_PAYLOAD] {json.dumps(invalid_rrn_payload, indent=4)}")
    # Call I4C API
    call_i4c_response_api(invalid_rrn_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'], log_file_name)
    logger.info(f"[RRN_VALIDATION] Sent status code {status_code} response for RRN: {rrn}")

    # Update DB
    db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
    db.bulk_update_record(
        incidents_table,
        {'job_id': data['job_id'], 'rrn': rrn},
        {'status': 'invalid' if status_code == "02" else 'statement unavailable', 'is_valid': False}
    )
