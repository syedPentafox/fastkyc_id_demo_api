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

        kvb_key = os.getenv("KVB_KEY_VALUE")
        kvb_endpoint = os.getenv("KVB_ENDPOINT", "")
        CASA_STMT_PATH = os.getenv("CASA_STMT_PATH", "")
        kvb_url = kvb_endpoint.rstrip("/") + "/" + CASA_STMT_PATH.lstrip("/")
        src_channel = os.getenv("KVB_SRC_CHANNEL")
        username = os.getenv("KVB_USERNAME")
        password = os.getenv("KVB_PASSWORD")
        userid = os.getenv("KVB_USERID")

        for idx, payload in enumerate(casa_stmt_payload):
            encrypted = aes_util.aes_encrypt(kvb_key, json.dumps(payload))
            logger.info(f"[KVB_ENCRYPTED] {encrypted}")
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
                logger.info(f"[KVB_API_REQUEST] {json.dumps(post_payload, indent=4)}")
                resp = requests.post(kvb_url, json=post_payload, timeout=30)
                logger.info(f"[KVB_API_RESPONSE] {resp.status_code} {resp.text}")
                # Try to decrypt the response if possible
                try:
                    resp_json = resp.json()
                    encrypt_res = resp_json.get("out_msg", {}).get("encryptRes")
                    if encrypt_res:
                        logger.info(f"[KVB_ENCRYPTED_RESPONSE] {encrypt_res}")
                        # Decrypt the response
                        decrypted = aes_util.aes_decrypt(kvb_key, encrypt_res)
                        decrypted_obj = json.loads(decrypted)
                        # Check for error keys and values
                        error_code = decrypted_obj.get("ErrorCode")
                        error_message = decrypted_obj.get("ErrorMessage")
                        if (
                            (error_code is not None and str(error_code) != "0") or
                            (error_message is not None and str(error_message).lower() != "success")
                        ):
                            logger.error(f"[KVB_ERROR_RESPONSE] {json.dumps(decrypted_obj, indent=4)}")
                        else:
                            logger.info(f"[KVB_DECRYPTED_RESPONSE] {json.dumps(decrypted_obj, indent=4)}")
                        # Immediately call Payment Status Inquiry API
                        payment_status_path = os.getenv("PAYMENT_STATUS_INQUIRY_PATH", "/ESB/PaymentStatusInquiry")
                        payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")
                        rrn = incidents[idx].get("rrn", "")
                        mode_of_payment = instrument.get("mode_of_payment", "")
                        payment_status_dict = {
                            "Transaction_Ref_Number": rrn,
                            "Mode_Of_Payment": mode_of_payment
                        }
                        encrypted_payment_status = aes_util.aes_encrypt(kvb_key, json.dumps(payment_status_dict))
                        payment_status_post_payload = {
                            "in_msg": {
                                "Src_Channel": src_channel,
                                "UserName": username,
                                "Password": password,
                                # "UserId": userid,
                                "encryptReq": encrypted_payment_status
                            }
                        }
                        try:
                            logger.info(f"[KVB_PAYMENT_STATUS_API_ENDPOINT] {payment_status_url}")
                            logger.info(f"[KVB_PAYMENT_STATUS_API_REQUEST] {json.dumps(payment_status_post_payload, indent=4)}")
                            payment_status_resp = requests.post(payment_status_url, json=payment_status_post_payload, timeout=30)
                            logger.info(f"[KVB_PAYMENT_STATUS_API_RESPONSE] {payment_status_resp.status_code} {payment_status_resp.text}")
                            try:
                                payment_status_resp_json = payment_status_resp.json()
                                payment_status_encrypt_res = payment_status_resp_json.get("out_msg", {}).get("encryptRes")
                                if payment_status_encrypt_res:
                                    decrypted_payment_status = aes_util.aes_decrypt(kvb_key, payment_status_encrypt_res)
                                    logger.info(f"[KVB_PAYMENT_STATUS_DECRYPTED_RESPONSE] {decrypted_payment_status}")
                                    # Handle success/failure
                                    try:
                                        payment_status_decoded = json.loads(decrypted_payment_status)
                                        payment_status_error_code = payment_status_decoded.get("ErrorCode")
                                        payment_status_error_message = payment_status_decoded.get("ErrorMessage")
                                        if (str(payment_status_error_code) != "0" or str(payment_status_error_message).lower() != "success"):
                                            logger.error(f"[KVB_PAYMENT_STATUS_ERROR] {json.dumps(payment_status_decoded, indent=4)}")
                                        else:
                                            logger.info(f"[KVB_PAYMENT_STATUS_SUCCESS] {json.dumps(payment_status_decoded, indent=4)}")
                                    except Exception as payment_status_json_exc:
                                        logger.error(f"[KVB_PAYMENT_STATUS_DECODE_ERROR] {payment_status_json_exc}")
                            except Exception as payment_status_dec_exc:
                                logger.error(f"[KVB_PAYMENT_STATUS_DECRYPT_ERROR] {payment_status_dec_exc}")
                        except Exception as payment_status_api_exc:
                            logger.error(f"[KVB_PAYMENT_STATUS_API_ERROR] {payment_status_api_exc}")
                        # ...existing hold funds logic below...
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
                                logger.info(f"[KVB_HOLD] NetBalance ({net_balance_float}) > Amount ({amount}): hold balance")
                                # HOLD FUND CASE
                                hold_fund_path = os.getenv("HOLD_FUND_PATH", "/ESB/ForceHoldMaintenance")
                                hold_fund_url = kvb_endpoint.rstrip("/") + "/" + hold_fund_path.lstrip("/")
                                today_str = datetime.now().strftime("%Y%m%d")
                                payload_data = data.get("payload", {})
                                instrument_data = payload_data.get("instrument", {})
                                acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                                payer_account_number = str(instrument_data.get("payer_account_number", ""))
                                transaction_branch = payer_account_number[:4] if len(payer_account_number) >= 4 else ""
                                cbs_user_id = str(userid)
                                hold_amount = "{:.2f}".format(float(incidents[idx].get("amount", 0)))
                                hold_fund_dict = {
                                    "CBSUserID": cbs_user_id,
                                    "TransactionBranch": transaction_branch,
                                    "AccountNumber": payer_account_number,
                                    "HoldAmount": hold_amount,
                                    "EarMarkType": "32",
                                    "Reason": "7",
                                    "Narration": acknowledgement_no,
                                    "ExpiryDate": "20991231",
                                    "TransactionType": "A",
                                    "HoldNumber": "",
                                    "TransactionDate": today_str
                                }
                                encrypted_hold = aes_util.aes_encrypt(kvb_key, json.dumps(hold_fund_dict))
                                hold_post_payload = {
                                    "in_msg": {
                                        "Src_Channel": src_channel,
                                        "UserName": username,
                                        "Password": password,
                                        # "UserId": userid,
                                        "encryptReq": encrypted_hold
                                    }
                                }
                                try:
                                    logger.info(f"[KVB_HOLD_API_ENDPOINT] {hold_fund_url}")
                                    logger.info(f"[KVB_HOLD_API_REQUEST] {json.dumps(hold_post_payload, indent=4)}")
                                    hold_resp = requests.post(hold_fund_url, json=hold_post_payload, timeout=30)
                                    logger.info(f"[KVB_HOLD_API_RESPONSE] {hold_resp.status_code} {hold_resp.text}")
                                    try:
                                        hold_resp_json = hold_resp.json()
                                        hold_encrypt_res = hold_resp_json.get("out_msg", {}).get("encryptRes")
                                        if hold_encrypt_res:
                                            decrypted_hold = aes_util.aes_decrypt(kvb_key, hold_encrypt_res)
                                            logger.info(f"[KVB_HOLD_DECRYPTED_RESPONSE] {decrypted_hold}")
                                    except Exception as hold_dec_exc:
                                        logger.error(f"[KVB_HOLD_DECRYPT_ERROR] {hold_dec_exc}")
                                except Exception as hold_api_exc:
                                    logger.error(f"[KVB_HOLD_API_ERROR] {hold_api_exc}")
                            else:
                                logger.info(f"[KVB_CANT_HOLD] NetBalance ({net_balance_float}) <= Amount ({amount}): can't hold full balance")
                except Exception as dec_exc:
                    logger.error(f"[CASA_STMT_DECRYPT_ERROR] {dec_exc}")
            except Exception as api_exc:
                logger.error(f"[CASA_STMT_API_ERROR] {api_exc}")
    except Exception as e:
        logger.error(f"[CASA_STMT_ERROR] {e}")
