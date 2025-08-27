import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import json
from utils.aes_encryption_decryption import AESUtil
import requests
from background_jobs.utils import is_response_success

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)

def casa_stmt_api(payload, kvb_key, kvb_url, src_channel, username, password, userid):
    logger.info('')
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
            decrypted_json = json.loads(decrypted)
            is_success = is_response_success(decrypted_json)
            logger.info(f"======= [CASA_STMT_END] =======")
            logger.info('')
            if is_success:
                return decrypted_json
            else:
                return None
        else:
            logger.error("[CASA_STMT_ERROR] No encrypted response found")
            logger.info(f"======= [CASA_STMT_END] =======")
            logger.info('')
            return None
    except Exception as exc:
        logger.error(f"[CASA_STMT_API_ERROR] {exc}")
        logger.info(f"======= [CASA_STMT_END] =======")
        logger.info('')
        return None
