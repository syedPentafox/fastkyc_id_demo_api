import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import os
import json
from utils.aes_encryption_decryption import AESUtil
import requests

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)

def casa_stmt_api(payload, kvb_key, kvb_url, src_channel, username, password, userid):
    logger.info(f"======= [CASA_STMT_START] =======")
    logger.info(f"[CASA_STMT_DICT] {json.dumps(payload, indent=4)}")
    encrypted_payload = AESUtil().aes_encrypt(kvb_key, json.dumps(payload))
    curl_data = json.dumps({
        "in_msg": {
            "Src_Channel": src_channel,
            "UserName": username,
            "Password": password,
            "UserId": userid,
            "encryptReq": encrypted_payload
        }
    })
    logger.info(f"[CASA_STMT_CURL] curl -X POST '{kvb_url}' -H 'Content-Type: application/json' -d '{curl_data}'")
    aes_util = AESUtil()
    encrypted = aes_util.aes_encrypt(kvb_key, json.dumps(payload))
    logger.info(f"[CASA_STMT_ENCRYPTED] {encrypted}")
    post_payload = {
        "in_msg": {
            "Src_Channel": src_channel,
            "UserName": username,
            "Password": password,
            "UserId": userid,
            "encryptReq": encrypted
        }
    }
    try:
        logger.info(f"[CASA_STMT_API_REQUEST] {json.dumps(post_payload, indent=4)}")
        resp = requests.post(kvb_url, json=post_payload, timeout=30)
        logger.info(f"[CASA_STMT_API_RESPONSE] {resp.status_code} {resp.text}")
        resp_json = resp.json()
        encrypt_res = resp_json.get("out_msg", {}).get("encryptRes")
        if encrypt_res:
            logger.info(f"[CASA_STMT_ENCRYPTED_RESPONSE] {encrypt_res}")
            decrypted = aes_util.aes_decrypt(kvb_key, encrypt_res)
            logger.info(f"[CASA_STMT_DECRYPTED_RESPONSE] {decrypted}")
            logger.info(f"======= [CASA_STMT_END] =======")
            return json.loads(decrypted)
        else:
            # FIXME: error in KVB_ENDPOINT
            logger.error("[CASA_STMT_ERROR] No encrypted response found")
            logger.info(f"======= [CASA_STMT_END] =======")
            return None
    except Exception as exc:
        # FIXME: error in KVB_ENDPOINT
        logger.error(f"[CASA_STMT_API_ERROR] {exc}")
        logger.info(f"======= [CASA_STMT_END] =======")
        return None
