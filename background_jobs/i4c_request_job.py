import logging
import os


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



import json
from datetime import datetime
from utils.aes_encryption_decryption import AESUtil
import requests
from background_jobs.payment_status_inquiry_api import payment_status_inquiry_api
from background_jobs.casa_stmt_api import casa_stmt_api

def i4c_request_job(request_json: str):
    try:
        data = json.loads(request_json)
        instrument = data.get("payload", {}).get("instrument", {})
        account_number = instrument.get("payer_account_number", "")
        txn_branch = account_number[:4] if len(account_number) >= 4 else ""
        incidents = instrument.get("incidents", [])
        kvb_key = os.getenv("KVB_KEY_VALUE")
        kvb_endpoint = os.getenv("KVB_ENDPOINT", "")
        CASA_STMT_PATH = os.getenv("CASA_STMT_PATH", "")
        kvb_url = kvb_endpoint.rstrip("/") + "/" + CASA_STMT_PATH.lstrip("/")
        src_channel = os.getenv("KVB_SRC_CHANNEL")
        username = os.getenv("KVB_USERNAME")
        password = os.getenv("KVB_PASSWORD")
        userid = os.getenv("KVB_USERID")

        for idx, incident in enumerate(incidents):
            # =======
            # CASA STMT Inquiry API
            # =======
            txn_ref_no = incident.get("rrn", "")
            raw_date = incident.get("transaction_date", "")
            formatted_date = datetime.strptime(raw_date, "%Y-%m-%d").strftime("%d-%m-%Y") if raw_date else raw_date
            casa_stmt_payload = {
                "TxnBranch": txn_branch,
                "TxnRefNo": txn_ref_no,
                "AccountNumber": account_number,
                "FromDate": formatted_date,
                "ToDate": formatted_date
            }
            decrypted_obj = casa_stmt_api(
                casa_stmt_payload,
                kvb_key,
                kvb_url,
                src_channel,
                username,
                password,
                userid
            )
            error_code = decrypted_obj.get("ErrorCode") if decrypted_obj is not None else None
            error_message = decrypted_obj.get("ErrorMessage") if decrypted_obj is not None else None

            # =======
            # PAYMENT STATUS Inquiry API
            # =======
            payment_status_path = os.getenv("PAYMENT_STATUS_INQUIRY_PATH", "/ESB/PaymentStatusInquiry")
            payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")
            rrn = incident.get("rrn", "")
            mode_of_payment = instrument.get("mode_of_payment", "")
            payment_status_dict = {
                "Transaction_Ref_Number": rrn,
                "Mode_Of_Payment": mode_of_payment
            }
            try:
                payment_status_response = payment_status_inquiry_api(
                    payment_status_dict,
                    kvb_key,
                    payment_status_url,
                    src_channel,
                    username,
                    password
                )
            except Exception as psi_exc:
                logger.error(f"[PAYMENT_STATUS_INQUIRY_ERROR] {psi_exc}")

            # ========
            # Check if both CASA STMT and Payment Status Inquiry were successful
            # ========
            casa_stmt_success = False
            if decrypted_obj is not None:
                error_code = decrypted_obj.get("ErrorCode")
                error_message = decrypted_obj.get("ErrorMessage")
                casa_stmt_success = (
                    error_code is not None and str(error_code) == "0" and
                    error_message is not None and str(error_message).lower() == "success"
                )
            payment_status_success = False
            if payment_status_response is not None:
                ps_error_code = payment_status_response.get("ErrorCode")
                ps_error_message = payment_status_response.get("ErrorMessage")
                payment_status_success = (
                    ps_error_code is not None and str(ps_error_code) == "0" and
                    ps_error_message is not None and str(ps_error_message).lower() == "success"
                )

            # =======
            # If both APIs were successful, go to the decision for the balance
            # =======
            if casa_stmt_success and payment_status_success:
                    net_balance = decrypted_obj.get("NetBalance") if decrypted_obj is not None else None
                    net_balance_float = float(net_balance) if net_balance not in [None, "", False] else 0.0
                    amount = float(incident.get("amount", 0)) if incident.get("amount", 0) not in [None, "", False] else 0.0
                    if net_balance_float > amount:
                        logger.info(f"[KVB_HOLD] NetBalance ({net_balance_float}) > Amount ({amount}): hold balance")
                        hold_fund_path = os.getenv("HOLD_FUND_PATH", "/ESB/ForceHoldMaintenance")
                        hold_fund_url = kvb_endpoint.rstrip("/") + "/" + hold_fund_path.lstrip("/")
                        today_str = datetime.now().strftime("%Y%m%d")
                        payload_data = data.get("payload", {})
                        instrument_data = payload_data.get("instrument", {})
                        acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                        payer_account_number = str(instrument_data.get("payer_account_number", ""))
                        transaction_branch = payer_account_number[:4] if len(payer_account_number) >= 4 else ""
                        cbs_user_id = str(userid)
                        hold_amount = "{:.2f}".format(float(incident.get("amount", 0)))
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
                        encrypted_hold = AESUtil().aes_encrypt(kvb_key, json.dumps(hold_fund_dict))
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
                            hold_resp_json = hold_resp.json()
                            hold_encrypt_res = hold_resp_json.get("out_msg", {}).get("encryptRes")
                            if hold_encrypt_res:
                                decrypted_hold = AESUtil().aes_decrypt(kvb_key, hold_encrypt_res)
                                logger.info(f"[KVB_HOLD_DECRYPTED_RESPONSE] {decrypted_hold}")
                        except Exception as hold_api_exc:
                            logger.error(f"[KVB_HOLD_API_ERROR] {hold_api_exc}")
                    else:
                        logger.info(f"[KVB_CANT_HOLD] NetBalance ({net_balance_float}) <= Amount ({amount}): can't hold full balance")
            else:
                logger.info("[KVB_SKIP_HOLD] Either CASA STMT or Payment Status Inquiry failed, skipping hold funds step.")
    except Exception as e:
        logger.error(f"[CASA_STMT_ERROR] {e}")
