
import os
import logging
import json
import requests
from .background_jobs_file_logger import add_background_jobs_file_handler
from utils.aes_encryption_decryption import AESUtil
from .utils import is_response_success

logger = logging.getLogger("JOB_RRN_LOGGER")
# logger.setLevel(logging.INFO)
# add_background_jobs_file_handler(logger)

def call_account_address_fetch_api(account_number):
    """
    Calls the KVB Account Address Fetch API.

    Args:
        account_number (str): The account number to fetch the address for.
        kvb_key (str): The AES key for encryption/decryption.
        src_channel (str): Source channel for the API call.
        username (str): API username.
        password (str): API password.

    Returns:
        dict: The decrypted address information on success, None on failure.
    """
    kvb_endpoint = os.environ.get("KVB_ENDPOINT", "")
    account_address_fetch_path = os.environ.get("ACCOUNT_ADDRESS_FETCH_PATH", "")
    kvb_key = os.environ.get("KVB_KEY_VALUE", "")
    src_channel = os.environ.get("KVB_SRC_CHANNEL", "")
    username = os.environ.get("KVB_USERNAME", "")
    password = os.environ.get("KVB_PASSWORD", "")
    api_url = kvb_endpoint.rstrip("/") + "/" + account_address_fetch_path.lstrip("/")

    logger.info("======= [ACCOUNT_ADDRESS_FETCH_START] =======")

    address_fetch_payload = {
        "AccountNumber": account_number
    }
    encrypted_payload = AESUtil().aes_encrypt(kvb_key, json.dumps(address_fetch_payload))
    post_payload = {
        "inputVariables": {
            "in_msg": {
                "Src_Channel": src_channel,
                "UserName": username,
                "Password": password,
                "encryptReq": encrypted_payload
            }
        }
    }

    try:
        logger.info(f"[KVB_ACCOUNT_ADDRESS_API_ENDPOINT] {api_url}")
        logger.info(f"[KVB_ACCOUNT_ADDRESS_API_REQUEST] {json.dumps(post_payload, indent=4)}")
        response = requests.post(api_url, json=post_payload, timeout=30)
        logger.info(f"[KVB_ACCOUNT_ADDRESS_API_RESPONSE] {response.status_code} {response.text}")
        response.raise_for_status()
        response_json = response.json()
        encrypted_response = response_json.get("out_msg", {}).get("encryptRes")
        if encrypted_response:
            decrypted_data = AESUtil().aes_decrypt(kvb_key, encrypted_response)
            logger.info(f"[KVB_ACCOUNT_ADDRESS_DECRYPTED_RESPONSE] {decrypted_data}")
            try:
                decoded_response = json.loads(decrypted_data)
            except Exception as json_exc:
                logger.error(f"[KVB_ACCOUNT_ADDRESS_DECODE_ERROR] {json_exc}")
                return None
            if is_response_success(decoded_response):
                logger.info(f"[KVB_ACCOUNT_ADDRESS_SUCCESS] {json.dumps(decoded_response, indent=4)}")
                return decoded_response
            else:
                logger.error(f"[KVB_ACCOUNT_ADDRESS_ERROR] {json.dumps(decoded_response, indent=4)}")
                return None
        else:
            logger.error("[KVB_ACCOUNT_ADDRESS_ERROR] No encrypted response found")
            return None
    except Exception as api_exc:
        logger.error(f"[KVB_ACCOUNT_ADDRESS_API_ERROR] {api_exc}")
        return None
    finally:
        logger.info("======= [ACCOUNT_ADDRESS_FETCH_END] =======")
