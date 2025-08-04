import os
import requests
from utils.aes_encryption_decryption import AESUtil
import logging

logger = logging.getLogger(__name__)


def upi_payment_status_inquiry_api(payload, kvb_key, upi_payment_status_url, src_channel, username, password):
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
    headers = {
        "Content-Type": "application/json",
        "src_channel": src_channel,
        "username": username,
        "password": password
    }
    try:
        response = requests.post(upi_payment_status_url, json=payload, headers=headers, timeout=30)
        response.raise_for_status()
        resp_json = response.json()
        logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Raw response: {resp_json}")
        # Decrypt if 'data' key present
        if isinstance(resp_json, dict) and resp_json.get('data'):
            try:
                decrypted = AESUtil.decrypt(resp_json['data'], kvb_key)
                logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Decrypted response: {decrypted}")
                return decrypted
            except Exception as dec_exc:
                logger.warning(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Decryption failed: {dec_exc}")
                return resp_json
        return resp_json
    except Exception as exc:
        logger.error(f"[UPI_PAYMENT_STATUS_INQUIRY_API] Error: {exc}")
        return {"error": str(exc)}
