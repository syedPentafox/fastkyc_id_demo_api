import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import json
import os
from utils.aes_encryption_decryption import AESUtil
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)

def payment_status_inquiry_api(payment_status_dict, kvb_key, payment_status_url, src_channel, username, password):
    logger.info(f"======= [PAYMENT_STATUS_INQUIRY_START] =======")
    logger.info(f"[PAYMENT_STATUS_DICT] {json.dumps(payment_status_dict, indent=4)}")
    encrypted_payment_status = AESUtil().aes_encrypt(kvb_key, json.dumps(payment_status_dict))
    curl_data = json.dumps({
        "inputVariables": {
            "in_msg": {
                "Src_Channel": src_channel,
                "UserName": username,
                "Password": password,
                "encryptReq": encrypted_payment_status
            }
        }
    })
    logger.info(f"[PAYMENT_STATUS_INQUIRY_CURL] curl -X POST '{payment_status_url}' -H 'Content-Type: application/json' -d '{curl_data}'")
    encrypted_payment_status = AESUtil().aes_encrypt(kvb_key, json.dumps(payment_status_dict))
    payment_status_post_payload = {
        "inputVariables": {
            "in_msg": {
                "Src_Channel": src_channel,
                "UserName": username,
                "Password": password,
                "encryptReq": encrypted_payment_status
            }
        }
    }
    try:
        logger.info(f"[KVB_PAYMENT_STATUS_API_ENDPOINT] {payment_status_url}")
        logger.info(f"[KVB_PAYMENT_STATUS_API_REQUEST] {json.dumps(payment_status_post_payload, indent=4)}")
        payment_status_resp = requests.post(payment_status_url, json=payment_status_post_payload, timeout=30)
        logger.info(f"[KVB_PAYMENT_STATUS_API_RESPONSE] {payment_status_resp.status_code} {payment_status_resp.text}")
        payment_status_resp_json = payment_status_resp.json()
        payment_status_encrypt_res = payment_status_resp_json.get("out_msg", {}).get("encryptRes")
        if payment_status_encrypt_res:
            decrypted_payment_status = AESUtil().aes_decrypt(kvb_key, payment_status_encrypt_res)
            logger.info(f"[KVB_PAYMENT_STATUS_DECRYPTED_RESPONSE] {decrypted_payment_status}")
            try:
                payment_status_decoded = json.loads(decrypted_payment_status)
                payment_status_error_code = payment_status_decoded.get("ErrorCode")
                payment_status_error_message = payment_status_decoded.get("ErrorMessage")
                if (str(payment_status_error_code) != "0" or str(payment_status_error_message).lower() != "success"):
                    # FIXME: error in KVB_ENDPOINT
                    logger.error(f"[KVB_PAYMENT_STATUS_ERROR] {json.dumps(payment_status_decoded, indent=4)}")
                else:
                    logger.info(f"[KVB_PAYMENT_STATUS_SUCCESS] {json.dumps(payment_status_decoded, indent=4)}")
            except Exception as payment_status_json_exc:
                # FIXME: error in KVB_ENDPOINT
                logger.error(f"[KVB_PAYMENT_STATUS_DECODE_ERROR] {payment_status_json_exc}")
            return payment_status_decoded
        else:
            # FIXME: error in KVB_ENDPOINT
            logger.error("[KVB_PAYMENT_STATUS_ERROR] No encrypted response found")
            return None
    except Exception as payment_status_api_exc:
        # FIXME: error in KVB_ENDPOINT
        logger.error(f"[KVB_PAYMENT_STATUS_API_ERROR] {payment_status_api_exc}")
        return None
