import logging
import os


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



import json
from datetime import datetime
from utils.aes_encryption_decryption import AESUtil
import requests

def casa_stmt_inquiry(request_json: str):
    try:
        data = json.loads(request_json)
        instrument = data.get("payload", {}).get("instrument", {})
        account_number = instrument.get("payer_account_number", "")
        txn_branch = account_number[:4] if len(account_number) >= 4 else ""
        incidents = instrument.get("incidents", [])
        casa_stmt_payload = []
        for incident in incidents:
            txn_ref_no = incident.get("rrn", "")
            # Format date from '2025-06-19' to '19-06-2025'
            raw_date = incident.get("transaction_date", "")
            try:
                formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y")
            except Exception:
                formatted_date = raw_date
            d = {
                "TxnBranch": txn_branch,
                "TxnRefNo": txn_ref_no,
                "AccountNumber": account_number,
                "FromDate": formatted_date,
                "ToDate": formatted_date
            }
            casa_stmt_payload.append(d)

        logger.info(f"[CASA_STMT_ALL_DICTS] {json.dumps(casa_stmt_payload, indent=4)}")

        # Encrypt, log, and POST each dict
        aes_util = AESUtil()
        casa_stmt_key = os.getenv("CASA_STMT_KEY_VALUE")
        casa_stmt_url = os.getenv("CASA_STMT_URL")
        src_channel = os.getenv("CASA_STMT_SRC_CHANNEL")
        username = os.getenv("CASA_STMT_USERNAME")
        password = os.getenv("CASA_STMT_PASSWORD")
        userid = os.getenv("CASA_STMT_USERID")

        for payload in casa_stmt_payload:
            encrypted = aes_util.aes_encrypt(casa_stmt_key, json.dumps(payload))
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
                resp = requests.post(casa_stmt_url, json=post_payload, timeout=30)
                logger.info(f"[CASA_STMT_API_RESPONSE] {resp.status_code} {resp.text}")
                # Try to decrypt the response if possible
                try:
                    resp_json = resp.json()
                    encrypt_res = resp_json.get("out_msg", {}).get("encryptRes")
                    if encrypt_res:
                        logger.info(f"[CASA_STMT_ENCRYPTED_RESPONSE] {encrypt_res}")
                        # Decrypt the response
                        decrypted = aes_util.aes_decrypt(casa_stmt_key, encrypt_res)
                        decrypted_obj = json.loads(decrypted)
                        logger.info(f"[CASA_STMT_DECRYPTED_RESPONSE] {json.dumps(decrypted_obj, indent=4)}")
                except Exception as dec_exc:
                    logger.error(f"[CASA_STMT_DECRYPT_ERROR] {dec_exc}")
            except Exception as api_exc:
                logger.error(f"[CASA_STMT_API_ERROR] {api_exc}")
    except Exception as e:
        logger.error(f"[CASA_STMT_ERROR] {e}")
