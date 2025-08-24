import os
import requests
from utils.aes_encryption_decryption import AESUtil
import logging
import json

logger = logging.getLogger(__name__)


def upi_payment_status_inquiry_api(payload, kvb_key, upi_payment_status_url, src_channel, username, password):
    # ...existing code...
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
        if upi_encrypt_res:
            try:
                decrypted = aes_util.aes_decrypt(kvb_key, upi_encrypt_res)
                logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Decrypted response: {decrypted}")
                return json.loads(decrypted)
            except Exception as dec_exc:
                # FIXME: error in KVB_ENDPOINT
                logger.warning(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Decryption failed: {dec_exc}")
                return resp_json
        return resp_json
    except Exception as exc:
        # FIXME: error in KVB_ENDPOINT
        logger.error(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Error: {exc}")
        return None
