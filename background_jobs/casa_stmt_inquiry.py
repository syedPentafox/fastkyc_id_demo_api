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

        for idx, payload in enumerate(casa_stmt_payload):
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
                        # Check for error keys and values
                        error_code = decrypted_obj.get("ErrorCode")
                        error_message = decrypted_obj.get("ErrorMessage")
                        if (
                            (error_code is not None and str(error_code) != "0") or
                            (error_message is not None and str(error_message).lower() != "success")
                        ):
                            logger.error(f"[CASA_STMT_ERROR_RESPONSE] {json.dumps(decrypted_obj, indent=4)}")
                            continue
                        logger.info(f"[CASA_STMT_DECRYPTED_RESPONSE] {json.dumps(decrypted_obj, indent=4)}")
                        # NetBalance check
                        net_balance = decrypted_obj.get("NetBalance")
                        try:
                            net_balance_float = float(net_balance) if net_balance is not None else None
                        except Exception:
                            net_balance_float = None
                        # Get amount from corresponding incident
                        try:
                            amount = float(incidents[idx].get("amount", 0))
                        except Exception:
                            amount = 0
                        if net_balance_float is not None:
                            if net_balance_float > amount:
                                logger.info(f"[CASA_STMT_HOLD] NetBalance ({net_balance_float}) > Amount ({amount}): hold balance")
                            else:
                                logger.info(f"[CASA_STMT_CANT_HOLD] NetBalance ({net_balance_float}) <= Amount ({amount}): can't hold full balance")
                except Exception as dec_exc:
                    logger.error(f"[CASA_STMT_DECRYPT_ERROR] {dec_exc}")
            except Exception as api_exc:
                logger.error(f"[CASA_STMT_API_ERROR] {api_exc}")
    except Exception as e:
        logger.error(f"[CASA_STMT_ERROR] {e}")
