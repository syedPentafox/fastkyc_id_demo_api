import os
import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import json
from utils.aes_encryption_decryption import AESUtil
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)
from utils.db_connection import db

def call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, received_dt):
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
                    'rrn': i4c_payload['transactions'][0].get('rrn_transaction_id', ''),
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
