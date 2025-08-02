import os
import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import json
from utils.aes_encryption_decryption import AESUtil
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)

def call_i4c_response_api(data, incident, casa_stmt_res, kvb_key, kvb_endpoint, hold_amount):
    payload_data = data.get("payload", {})
    acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
    job_id = str(data.get("job_id", ""))
    # CASA STMT response fields
    pan_number = casa_stmt_res.get("PAN", "")
    ifsc_code = casa_stmt_res.get("IFSCCode", "")
    net_balance = casa_stmt_res.get("NetBalance", None)
    # Get payer_account_number and rrn from i4c request
    payer_account_number = ""
    rrn = ""
    instrument_data = payload_data.get("instrument", {})
    payer_account_number = str(instrument_data.get("payer_account_number", ""))
    transaction_datetime_val = incident.get("transaction_datetime") + " " + incident.get("transaction_time")
    amount = hold_amount
    i4c_payload = {
        "acknowledgement_no": acknowledgement_no,
        "job_id": job_id,
        "transactions": [
            {
                "txn_type": "Transaction Put on Hold",
                "txn_type_id": "1",
                "amount": amount,
                "transaction_datetime": transaction_datetime_val,
                "phone_number": "1234567890",
                "email": "testing@gmail.com",
                "pan_number": pan_number,
                "ifsc_code": ifsc_code,
                "root_account_number": payer_account_number,
                "root_rrn_transaction_id": rrn,
                "root_bankid": "25",
                "status_code": "00",
                "root_effective_balance": str(net_balance),
                "root_ifsc_code": ifsc_code,
                "remarks": acknowledgement_no
            }
        ]
    }
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
    try:
        i4c_resp = requests.post(i4c_response_url, json=i4c_post_payload, timeout=30)
        logger.info(f"[I4C_RESPONSE_API_RESPONSE] {i4c_resp.status_code} {i4c_resp.text}")
        i4c_resp_json = i4c_resp.json()
        i4c_encrypt_res = i4c_resp_json.get("out_msg", {}).get("encryptRes")
        if i4c_encrypt_res:
            decrypted_i4c = aes_util.aes_decrypt(kvb_key, i4c_encrypt_res)
            logger.info(f"[I4C_RESPONSE_DECRYPTED_RESPONSE] {decrypted_i4c}")
        else:
            logger.error("[I4C_RESPONSE_ERROR] No encrypted response found in I4C response")
    except Exception as i4c_exc:
        logger.error(f"[I4C_RESPONSE_API_ERROR] {i4c_exc}")
