import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import os
from background_jobs.hold_funds_api import call_hold_funds_api
from .i4c_response_api import call_i4c_response_api


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)



import json
from datetime import datetime
from utils.aes_encryption_decryption import AESUtil
import requests
from background_jobs.payment_status_inquiry_api import payment_status_inquiry_api
from background_jobs.casa_stmt_api import casa_stmt_api
import uuid

def i4c_request_job(request_json: str):
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
    payment_status_path = os.getenv("PAYMENT_STATUS_INQUIRY_PATH", "/ESB/PaymentStatusInquiry")
    hold_fund_path = os.getenv("HOLD_FUND_PATH", "/ESB/ForceHoldMaintenance")

    for idx, incident in enumerate(incidents):
            # =======
            # CASA STMT Inquiry API
            # =======
            # Generate a unique alphanumeric txn_ref_no (max length 30)
            txn_ref_no = uuid.uuid4().hex[:30]
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

            # # =======
            # # PAYMENT STATUS Inquiry API
            # # =======
            # payment_status_path = os.getenv("PAYMENT_STATUS_INQUIRY_PATH", "/ESB/PaymentStatusInquiry")
            # payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")
            # rrn = incident.get("rrn", "")
            # mode_of_payment = instrument.get("mode_of_payment", "")
            # payment_status_dict = {
            #     "Transaction_Ref_Number": rrn,
            #     "Mode_Of_Payment": mode_of_payment
            # }
            # try:
            #     payment_status_response = payment_status_inquiry_api(
            #         payment_status_dict,
            #         kvb_key,
            #         payment_status_url,
            #         src_channel,
            #         username,
            #         password
            #     )
            # except Exception as psi_exc:
            #     logger.error(f"[PAYMENT_STATUS_INQUIRY_ERROR] {psi_exc}")

            # ========
            # Check if both CASA STMT and Payment Status Inquiry were successful
            # Only check if CASA STMT API was successful
            # ========
            casa_stmt_success = False
            if decrypted_obj is not None:
                error_code = decrypted_obj.get("ErrorCode")
                error_message = decrypted_obj.get("ErrorMessage")
                casa_stmt_success = (
                    error_code is not None and str(error_code) == "0" and
                    error_message is not None and str(error_message).lower() == "success"
                )
            # payment_status_success = False
            # if payment_status_response is not None:
            #     ps_error_code = payment_status_response.get("ErrorCode")
            #     ps_error_message = payment_status_response.get("ErrorMessage")
            #     payment_status_success = (
            #         ps_error_code is not None and str(ps_error_code) == "0" and
            #         ps_error_message is not None and str(ps_error_message).lower() == "success"
            #     )

            # =======
            # If CASA API was successful, go to the decision for the balance
            # =======
            # if casa_stmt_success and payment_status_success:
            if casa_stmt_success:
                net_balance = decrypted_obj.get("NetBalance")
                net_balance_float = float(net_balance) if net_balance else 0.0
                disputed_amount = float(incident.get("disputed_amount", 0) or 0)
                disputed_amount_float = float(disputed_amount) if disputed_amount else 0.0
                if net_balance_float > disputed_amount:
                    # =======
                    # Hold Funds API
                    # =======
                    logger.info(f"[KVB_HOLD] NetBalance ({net_balance_float}) > DisputedAmount ({disputed_amount}): hold disputed amount")
                    call_hold_funds_api(
                        kvb_endpoint=kvb_endpoint,
                        hold_fund_path=hold_fund_path,
                        disputed_amount=disputed_amount,
                        data=data,
                        userid=userid,
                        kvb_key=kvb_key,
                        src_channel=src_channel,
                        username=username,
                        password=password
                    )

                    # =======
                    # Call I4C response API after hold
                    # =======
                    logger.info("[CALL_I4C_RESPONSE_API] Call I4C response API after hold")
                    hold_amount = "{:.2f}".format(disputed_amount)
                    call_i4c_response_api(data, incident, decrypted_obj, kvb_key, kvb_endpoint, hold_amount)
                else:
                    # =======
                    # Hold Net Balance only
                    # =======
                    logger.info(f"[KVB_CANT_HOLD] NetBalance ({net_balance_float}) <= DisputedAmount ({disputed_amount}): can't hold disputed amount")
                    logger.info(f"[KVB_CANT_HOLD] Holding {net_balance_float} Net Balance only")
                    call_hold_funds_api(
                        kvb_endpoint=kvb_endpoint,
                        hold_fund_path=hold_fund_path,
                        disputed_amount=net_balance,
                        data=data,
                        userid=userid,
                        kvb_key=kvb_key,
                        src_channel=src_channel,
                        username=username,
                        password=password
                    )

                    # =======
                    # Call I4C response API after hold
                    # =======
                    logger.info("[CALL_I4C_RESPONSE_API] Call I4C response API after hold")
                    hold_amount = "{:.2f}".format(net_balance)
                    call_i4c_response_api(data, incident, decrypted_obj, kvb_key, kvb_endpoint, hold_amount)

                    # =======
                    # Calculate pending amount
                    # =======
                    pending_amount_float = disputed_amount_float - net_balance_float
                    logger.info(f"[AFTER_HOLD] Pending Amount: {pending_amount_float}")
            else:
                logger.info("CASA STMT failed.")
