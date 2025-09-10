import os
import requests
from utils.aes_encryption_decryption import AESUtil
import logging
import json

from .background_jobs_file_logger import add_background_jobs_file_handler

def upi_payment_status_inquiry_api(payload, kvb_key, upi_payment_status_url, src_channel, username, password, log_file_name):
    """
    Calls the UPI Payment Status Inquiry API and returns the decrypted response if applicable.
    Args:
        payload (dict): The payload for the UPI inquiry (ReferenceId, TxnDate).
        kvb_key (str): The AES key for decryption.
        upi_payment_status_url (str): The endpoint URL.
        src_channel (str): Source channel.
        username (str): API username.
        password (str): API password.
    Returns:
        dict: Decrypted response or raw response if decryption not needed.
    """
    logger = logging.getLogger(log_file_name)
    aes_util = AESUtil()
    encrypted_upi_payload = aes_util.aes_encrypt(kvb_key, json.dumps(payload))
    upi_post_payload = {
        "in_msg": {
            "Src_Channel": src_channel,
            "UserName": username,
            "Password": password,
            "encryptReq": encrypted_upi_payload
        }
    }
    try:
        logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Request: {json.dumps(upi_post_payload)}")
        response = requests.post(upi_payment_status_url, json=upi_post_payload, timeout=30)
        logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Response: {response.status_code} {response.text}")
        response.raise_for_status()
        resp_json = response.json()
        upi_encrypt_res = resp_json.get("out_msg", {}).get("encryptRes")
        upi_decrypt_res = aes_util.aes_decrypt(kvb_key, upi_encrypt_res)
        decrypted = json.loads(upi_decrypt_res)
        logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Decrypted response: {decrypted}")
        status_error_code = decrypted.get("ErrorCode")
        status_error_message = decrypted.get("ErrorMessage")
        if (str(status_error_code) == "0" or str(status_error_message).lower() == "success"):
            try:
                return decrypted
            except Exception as dec_exc:
                # FIXME: error in KVB_ENDPOINT
                logger.warning(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Decryption failed: {dec_exc}")
                return resp_json
        return None
    except Exception as exc:
        # FIXME: error in KVB_ENDPOINT
        logger.error(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Error: {exc}")
        return None

