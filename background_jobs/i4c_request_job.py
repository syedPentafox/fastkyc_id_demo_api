import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import os
from background_jobs.hold_funds_api import call_hold_funds_api
import re
from .i4c_response_api import call_i4c_response_api
from background_jobs.other_i4c_responses import money_transfer_to_non_upi, money_transfer_to_upi, non_money_transfer_to


# logger = logging.getLogger(__name__)
# logger.setLevel(logging.INFO)
# add_background_jobs_file_handler(logger)



import json
from datetime import datetime
from utils.aes_encryption_decryption import AESUtil
from background_jobs.payment_status_inquiry_api import payment_status_inquiry_api
from background_jobs.upi_payment_status_inquiry_api import upi_payment_status_inquiry_api
from background_jobs.casa_stmt_api import casa_stmt_api
import uuid

from background_jobs.account_address_fetch_api import call_account_address_fetch_api

from utils.db_connection import db
from background_jobs.utils import fraud_type_table_prefix

def i4c_request_job(request_json: str):
    data = request_json
    #logger.info(json.dumps(data, indent=4))
    # logger.info('i4c_request_job request_json start')
    # logger.info(data)
    # logger.info('i4c_request_job request_json end')
    request = request_json.get('request')
    instrument = request_json.get('request').get('instrument')#data.get("request", {}).get("instrument", {})
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

    table_prefix = fraud_type_table_prefix.get(request['sub_category'])
    transactions_table = f"{table_prefix}_transactions"
    incidents_table = f"{table_prefix}_incidents"
    response_table = f"{table_prefix}_responses"

    db.create_record_(transactions_table, {
        'job_id': data['job_id'],
        'sub_category': request['sub_category'],
        'requestor': instrument['requestor'],
        'payer_bank_code': instrument['payer_bank_code'],
        'mode_of_payment': instrument['mode_of_payment'],
        'payer_mobile_number': instrument['payer_mobile_number'],
        'payer_account_number': instrument['payer_account_number'],
        'state': instrument['state'],
        'district': instrument['district'],
        'received_dt': data['received_dt'] 
    })

    db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'R'})

    # # Fetch phone_number and email from account address API before RRN validation
    # address_info = None
    # try:
    #     address_info = call_account_address_fetch_api(account_number)
    # except Exception as fetch_exc:
    #     logger.error(f"[ACCOUNT_ADDRESS_FETCH_API_ERROR] {fetch_exc}")

    # phone_number = address_info.get("MobileNo", "1234567890") if address_info else "1234567890"
    # # email = address_info.get("Email", "testing@gmail.com") if address_info else "testing@gmail.com"
    # email = address_info.get("Email", "") if address_info else ""

    for idx, incident in enumerate(incidents):
            # Convert 'YYYY-MM-DD' to 'DD-Month-YYYY' (e.g., 2022-12-04 -> 04-December-2022)
            txn_date_str = incident.get('transaction_date', '')
            try:
                txn_date_obj = datetime.strptime(txn_date_str, '%Y-%m-%d')
                formatted_txn_date = txn_date_obj.strftime('%d-%B-%Y')
            except Exception:
                formatted_txn_date = txn_date_str

            db.create_record_(incidents_table, {
                'ack_no': data['ack_no'],
                'job_id': data['job_id'],
                'amount': incident['amount'],
                'rrn': incident['rrn'],
                'transaction_date': formatted_txn_date,
                'transaction_time': incident['transaction_time'],
                'disputed_amount': incident['disputed_amount'],
                'layer': incident['layer'],
                'received_dt': data['received_dt'],
                'mode_of_payment': instrument['mode_of_payment'],
            })
            
            log_file_name = f'{data["job_id"]}--{incident["rrn"]}'
            logger = logging.getLogger(log_file_name)
            logger.setLevel(logging.INFO)
            LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), '../logs', f'{log_file_name}.log')
            file_handler = logging.FileHandler(LOG_FILE_PATH)
            file_handler.setLevel(logging.INFO)
            formatter = logging.Formatter('%(asctime)s %(levelname)s %(name)s %(message)s')
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

            logger.info('i4c_request_job request_json start')
            logger.info(data)
            logger.info('i4c_request_job request_json end')

            # Fetch phone_number and email from account address API before RRN validation
            address_info = None
            try:
                address_info = call_account_address_fetch_api(account_number, log_file_name)
            except Exception as fetch_exc:
                logger.error(f"[ACCOUNT_ADDRESS_FETCH_API_ERROR] {fetch_exc}")

            phone_number = address_info.get("MobileNo", "1234567890") if address_info else "1234567890"
            # email = address_info.get("Email", "testing@gmail.com") if address_info else "testing@gmail.com"
            email = (address_info.get("Email") if address_info else "") or ""


            # =======
            # CASA STMT Inquiry API
            # =======

            # Generate a unique alphanumeric txn_ref_no (max length 30)
            txn_ref_no = uuid.uuid4().hex[:30]

            # FromDate: transaction_date from incident (format: dd-mm-yyyy)
            from_date_raw = incident.get("transaction_date", "")
            from_date = datetime.strptime(from_date_raw, "%Y-%m-%d").strftime("%d-%m-%Y") if from_date_raw else from_date_raw
            
            # ToDate: received_dt from payload (format: dd-mm-yyyy)
            received_dt_raw = data.get("received_dt", "")
            to_date = received_dt_raw.strftime('%d-%m-%Y')

            casa_stmt_payload = {
                "TxnBranch": txn_branch,
                "TxnRefNo": txn_ref_no,
                "AccountNumber": account_number,
                "FromDate": from_date,
                "ToDate": to_date
            }
            decrypted_obj = casa_stmt_api(
                casa_stmt_payload,
                kvb_key,
                kvb_url,
                src_channel,
                username,
                password,
                userid,
                log_file_name
            )

            if not decrypted_obj:
                # =======
                # Account not found - Send status code 01 response and skip balance logic
                # =======
                logger.warning(f"[RRN_VALIDATION] Statement not found - not found in CASA transactions: {rrn}")
                
                # Prepare status 02 response payload with all hold API fields
                payload_data = data.get("request", {})
                acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                job_id = str(data.get("job_id", ""))
                instrument_data = payload_data.get("instrument", {})
                payer_account_number = str(instrument_data.get("payer_account_number", ""))
                
                # Get additional fields from CASA response (same as hold API)
                pan_number = decrypted_obj.get("PAN", "") or "FORM60"
                ifsc_code = decrypted_obj.get("IFSCCode", "")
                net_balance = decrypted_obj.get("NetBalance", None)
                disputed_amount = incident.get("disputed_amount", 0)
                disputed_amount_float = float(disputed_amount) if disputed_amount else 0.0
                amount = incident.get("amount", 0)
                amount_float = float(amount) if amount else 0.0
                
                # Use current timestamp for invalid RRN
                current_timestamp = datetime.now()
                transaction_datetime_val = current_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                amount_str = "{:.2f}".format(amount_float)
                disputed_amount_str = "{:.2f}".format(disputed_amount_float)
                
                invalid_rrn_payload = {
                    "acknowledgement_no": acknowledgement_no,
                    "job_id": job_id,
                    "transactions": [
                        {
                            # "txn_type": "Transaction Put on Hold",
                            # "txn_type_id": "1",
                            "amount": amount_str,
                            "transaction_datetime": transaction_datetime_val,
                            "disputed_amount": disputed_amount_str,
                            # "phone_number": phone_number,
                            # "email": email,
                            # "pan_number": pan_number,
                            # "ifsc_code": ifsc_code,
                            "root_account_number": payer_account_number,
                            "root_rrn_transaction_id": rrn,
                            "root_bankid": "25",
                            "status_code": "01",
                            # "root_effective_balance": str(net_balance),
                            # "root_ifsc_code": ifsc_code,
                            "remarks": acknowledgement_no
                        }
                    ]
                }
                
                call_i4c_response_api(invalid_rrn_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'], log_file_name)
                logger.info(f"[RRN_VALIDATION] Sent status code 02 response for invalid RRN: {rrn}")

                db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'statement unavailable', 'is_valid': False})
                
                # Skip balance logic for this incident
                continue

            # =======
            # If CASA API was successful, validate RRN before proceeding
            # =======
            if decrypted_obj:
                # =======
                # RRN Validation - Check if incident RRN, amount and datetime exist in CASA transactions
                # =======
                rrn = incident.get("rrn", "")
                incident_amount = incident.get("amount", 0)
                incident_date = incident.get("transaction_date", "")
                incident_time = incident.get("transaction_time", "")
                
                # Parse incident datetime
                incident_datetime = None
                try:
                    incident_datetime_str = f"{incident_date} {incident_time}"
                    incident_datetime = datetime.strptime(incident_date, "%Y-%m-%d")
                except Exception as date_exc:
                    logger.warning(f"[RRN_VALIDATION] Could not parse incident datetime: {incident_datetime_str}, error: {date_exc}")
                
                # Search for matching transaction in CASA
                casa_txn_details = decrypted_obj.get("CasaTransactionDetails", [])
                rrn_valid = False
                matched_casa_txn = None
                matched_index = None
                
                logger.info(f"[RRN_VALIDATION] Validating RRN: {rrn}, Amount: {incident_amount}, DateTime: {incident_datetime}")
                
                if transaction_type == "NEFT":
                    logger.info(f"[RRN_VALIDATION][NEFT] Applying NEFT-specific validation for RRN: {rrn}")

                    if len(rrn) >= 5 and rrn[4].upper() == "N":
                        logger.info(f"[RRN_VALIDATION][NEFT] 5th character is 'N'. Proceeding with payment inquiry API.")

                        payment_status_dict = {
                            "Transaction_Ref_Number": rrn,
                            "Mode_Of_Payment": transaction_type,
                        }
                        payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")

                        payment_status_response = payment_status_inquiry_api(
                            payment_status_dict,
                            kvb_key,
                            payment_status_url,
                            src_channel,
                            username,
                            password,
                            log_file_name,
                        )
                        logger.info(f"[RRN_VALIDATION][NEFT] Payment inquiry response: {payment_status_response}")

                        if (payment_status_response and isinstance(payment_status_response, dict)):
                            logger.info(f"[RRN_VALIDATION][NEFT] Valid RRN (Payment Inquiry success): {rrn}")
                            rrn_valid = True
                        else:
                            logger.warning(f"[RRN_VALIDATION][NEFT] Invalid RRN (Payment Inquiry failed): {rrn}")
                            rrn_valid = False
                    else:
                        logger.warning(f"[RRN_VALIDATION][NEFT] Invalid RRN - 5th character is not 'N': {rrn}")
                        rrn_valid = False
                if not rrn_valid and transaction_type != "NEFT":
                    for idx, casa_txn in enumerate(casa_txn_details):
                        txn_desc = casa_txn.get("TransactionDescription", "")
                        txn_amount_str = casa_txn.get("TransactionAmount", "0")
                        txn_date_str = casa_txn.get("TransactionDate", "")

                        # Check RRN match using string matching
                        if rrn and rrn in txn_desc:
                            # Check amount match (convert both to float)
                            try:
                                casa_amount = float(txn_amount_str)
                                incident_amount_float = float(incident_amount)

                                if casa_amount == incident_amount_float:
                                    # Check datetime match
                                    try:
                                        # Parse CASA datetime format: "18-02-2025 14:58:22"
                                        casa_datetime = datetime.strptime(txn_date_str, "%d-%m-%Y %H:%M:%S")

                                        if incident_datetime and casa_datetime.date() == incident_datetime.date():
                                            # All three conditions match (only date, ignoring time)
                                            rrn_valid = True
                                            matched_casa_txn = casa_txn
                                            matched_index = idx
                                            logger.info(
                                                f"[RRN_VALIDATION] Valid RRN found - RRN: {rrn}, Amount: {casa_amount}, Date: {casa_datetime.date()}"
                                            )
                                            break
                                        else:
                                            logger.info(
                                                f"[RRN_VALIDATION] RRN and amount match but date mismatch - Casa: {casa_datetime.date()}, Incident: {incident_datetime.date()}"
                                            )
                                    except Exception as casa_date_exc:
                                        logger.warning(
                                            f"[RRN_VALIDATION] Could not parse CASA datetime: {txn_date_str}, error: {casa_date_exc}"
                                        )
                                else:
                                    logger.info(
                                        f"[RRN_VALIDATION] RRN match but amount mismatch - Casa: {casa_amount}, Incident: {incident_amount_float}"
                                    )
                            except Exception as amount_exc:
                                logger.warning(f"[RRN_VALIDATION] Could not parse amounts for comparison: {amount_exc}")

                if not rrn_valid:
                    # =======
                    # RRN Invalid - Send status code 02 response and skip balance logic
                    # =======
                    logger.warning(f"[RRN_VALIDATION] Invalid RRN - not found in CASA transactions: {rrn}")
                    
                    # Prepare status 02 response payload with all hold API fields
                    payload_data = data.get("request", {})
                    acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                    job_id = str(data.get("job_id", ""))
                    instrument_data = payload_data.get("instrument", {})
                    payer_account_number = str(instrument_data.get("payer_account_number", ""))
                    
                    # Get additional fields from CASA response (same as hold API)
                    pan_number = decrypted_obj.get("PAN", "") or "FORM60"
                    ifsc_code = decrypted_obj.get("IFSCCode", "")
                    net_balance = decrypted_obj.get("NetBalance", None)
                    disputed_amount = incident.get("disputed_amount", 0)
                    disputed_amount_float = float(disputed_amount) if disputed_amount else 0.0
                    amount = incident.get("amount", 0)
                    amount_float = float(amount) if amount else 0.0
                    
                    # Use current timestamp for invalid RRN
                    current_timestamp = datetime.now()
                    transaction_datetime_val = current_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    amount_str = "{:.2f}".format(amount_float)
                    disputed_amount_str = "{:.2f}".format(disputed_amount_float)
                    
                    invalid_rrn_payload = {
                        "acknowledgement_no": acknowledgement_no,
                        "job_id": job_id,
                        "transactions": [
                            {
                                # "txn_type": "Transaction Put on Hold",
                                # "txn_type_id": "1",
                                "amount": amount_str,
                                "transaction_datetime": transaction_datetime_val,
                                "disputed_amount": disputed_amount_str,
                                # "phone_number": phone_number,
                                # "email": email,
                                # "pan_number": pan_number,
                                # "ifsc_code": ifsc_code,
                                "root_account_number": payer_account_number,
                                "root_rrn_transaction_id": rrn,
                                "root_bankid": "25",
                                "status_code": "02",
                                # "root_effective_balance": str(net_balance),
                                # "root_ifsc_code": ifsc_code,
                                "remarks": acknowledgement_no
                            }
                        ]
                    }
                    
                    call_i4c_response_api(invalid_rrn_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'], log_file_name)
                    logger.info(f"[RRN_VALIDATION] Sent status code 02 response for invalid RRN: {rrn}")

                    db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                    db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'invalid', 'is_valid': False})
                    
                    # Skip balance logic for this incident
                    continue
                
                logger.info(f"[RRN_VALIDATION] RRN validation passed for: {rrn}")
                
                mode_of_payment = instrument.get("mode_of_payment", "CREDIT").upper()
                transaction_type = instrument.get("transaction_type", "").upper()
                if mode_of_payment == "DEBIT" and transaction_type in ["IMPS", "NEFT", "RTGS", "UPI", "ATM", "POS", "CHQ PAID", "AEPS"]:
                    # For DEBIT, directly call payment inquiry API and then I4C response API
                    try:
                        if transaction_type in ["IMPS", "NEFT", "RTGS"]:
                            logger.info("DEBIT MONEY TRANSFER TO NON UPI")
                            rrn = incident.get('rrn', '')
                            #transaction_datetime = incident.get("transaction_date", "") + " " + incident.get("transaction_time", "")
                            transaction_datetime = casa_datetime.strftime('%Y-%m-%d %H:%M:%S')
                            amount = str(incident.get("amount", ""))
                            disputed_amount = str(incident.get('disputed_amount', ''))
                            payer_account_number = instrument.get("payer_account_number", "")
                            is_success = money_transfer_to_non_upi(decrypted_obj, data, transaction_type, response_table, rrn, transaction_datetime, amount, payer_account_number, disputed_amount, phone_number, email, rrn, log_file_name)
                            db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                            db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'success' if is_success else 'failure', 'is_valid': True})
                        elif transaction_type == "UPI":
                            txn_date_str = instrument.get("transaction_date", "")
                            txn_date_obj = datetime.strptime(txn_date_str, "%Y-%m-%d")
                            txn_date_formatted = txn_date_obj.strftime("%d-%b-%Y")
                            amount = str(instrument.get("amount", ""))
                            disputed_amount = str(instrument.get("disputed_amount", ""))
                            #transaction_datetime = incident.get("transaction_date", "") + " " + incident.get("transaction_time", "")
                            transaction_datetime = casa_datetime.strftime('%Y-%m-%d %H:%M:%S')
                            payer_account_number = instrument.get("payer_account_number", "")
                            is_success = money_transfer_to_upi(decrypted_obj, data, rrn, txn_date_formatted, amount, disputed_amount, transaction_datetime, payer_account_number, response_table, phone_number, email, rrn, log_file_name)
                            db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                            db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'success' if is_success else 'failure', 'is_valid': True})
                        elif transaction_type in ["ATM CSW", "POS/", "CHQ PAID", "AEPS"]:
                            payer_account_number = instrument.get("payer_account_number", "")
                            #transaction_datetime = incident.get("transaction_date", "") + " " + incident.get("transaction_time", "")
                            transaction_datetime = casa_datetime.strftime('%Y-%m-%d %H:%M:%S')
                            amount = str(instrument.get("amount", ""))
                            disputed_amount = str(instrument.get("disputed_amount", ""))
                            is_success = non_money_transfer_to(decrypted_obj, data, payer_account_number, txn, rrn, txn_desc, txn_amount, disputed_amt, response_table, transaction_datetime, phone_number, email, log_file_name)
                            db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                            db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'success' if is_success else 'failure', 'is_valid': True})
                    except Exception as debit_exc:
                        logger.error(f"[DEBIT_FLOW_ERROR] {debit_exc}")
                else:
                    net_balance = decrypted_obj.get("NetBalance")
                    net_balance_float = float(net_balance) if net_balance else 0.0
                    disputed_amount = incident.get("disputed_amount", 0)
                    disputed_amount_float = float(disputed_amount) if disputed_amount else 0.0
                    if net_balance_float > disputed_amount:
                        # =======
                        # Hold Funds API
                        # =======
                        # logger.info(f"[KVB_HOLD] NetBalance ({net_balance_float}) > DisputedAmount ({disputed_amount}): hold disputed amount")
                        logger.info(f"[KVB_HOLD] ({disputed_amount}): hold disputed amount")
                        
                        # Call hold funds API and capture the timestamp it used
                        is_hold_i4c_success = False
                        hold_timestamp, is_hold_success = call_hold_funds_api(
                            kvb_endpoint=kvb_endpoint,
                            hold_fund_path=hold_fund_path,
                            disputed_amount=disputed_amount_float,
                            data=data,
                            userid=userid,
                            kvb_key=kvb_key,
                            src_channel=src_channel,
                            username=username,
                            password=password,
                            log_file_name=log_file_name
                        )

                        if is_hold_success:
                            # =======
                            # Call I4C response API after hold
                            # =======
                            logger.info("[CALL_I4C_RESPONSE_API] Call I4C response API after hold")
                            payload_data = data.get("request", {})
                            acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                            job_id = str(data.get("job_id", ""))
                            # CASA STMT response fields
                            pan_number = decrypted_obj.get("PAN", "") or "FORM60"
                            ifsc_code = decrypted_obj.get("IFSCCode", "")
                            net_balance = decrypted_obj.get("NetBalance", None)
                            # Get payer_account_number and rrn from i4c request
                            payer_account_number = ""
                            rrn = ""
                            rrn = incident.get("rrn", "")
                            instrument_data = payload_data.get("instrument", {})
                            payer_account_number = str(instrument_data.get("payer_account_number", ""))
                            # Use the same server timestamp for I4C response
                            transaction_datetime_val = hold_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                            hold_amount = "{:.2f}".format(disputed_amount_float)
                            i4c_payload = {
                                "acknowledgement_no": acknowledgement_no,
                                "job_id": job_id,
                                "transactions": [
                                    {
                                        "txn_type": "Transaction Put on Hold",
                                        "txn_type_id": "1",
                                        "amount": hold_amount,
                                        "transaction_datetime": transaction_datetime_val,
                                        "phone_number": phone_number,
                                        "email": email,
                                        "pan_number": pan_number,
                                        "ifsc_code": ifsc_code,
                                        "root_account_number": payer_account_number,
                                        "root_rrn_transaction_id": rrn,
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "root_effective_balance": str(net_balance),
                                        "root_ifsc_code": ifsc_code,
                                        "remarks": acknowledgement_no
                                    }
                                ]
                            }
                            is_hold_i4c_success = call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'], log_file_name)

                            db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                            db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'success' if is_hold_i4c_success else 'failure', 'is_valid': True})
                    else:
                        #if net_balance_float <= 0:
                        #    # =======
                        #    # Cannot hold any amount or call I4C response API if net balance is negative
                        #    # =======
                        #    logger.warning(f"[KVB_NEGATIVE_BALANCE] NetBalance ({net_balance_float}) is negative. Cannot hold or call I4C response API.")
                        #    pending_amount_float = disputed_amount_float
                        #    logger.info(f"[AFTER_HOLD] Pending Amount: {pending_amount_float}")
                        #    is_hold_success = False
                        #    is_hold_i4c_success = False
                        #else:
                        if True:
                            # =======
                            # Hold Net Balance only
                            # =======
                            #logger.info(f"[KVB_CANT_HOLD] NetBalance ({net_balance_float}) <= DisputedAmount ({disputed_amount}): can't hold disputed amount")
                            # logger.info(f"[KVB_CANT_HOLD] Holding {net_balance_float} Net Balance only")
                            logger.info(f"[KVB_HOLD] ({disputed_amount}): hold disputed amount")

                            
                            # Call hold funds API and capture the timestamp it used
                            is_hold_i4c_success = False

                            # # NOTE: check for handling of 0 or negative balance
                            # net_balance_float = net_balance_float if net_balance_float > 0 else 1.23

                            hold_timestamp, is_hold_success = call_hold_funds_api(
                                kvb_endpoint=kvb_endpoint,
                                hold_fund_path=hold_fund_path,
                                disputed_amount=disputed_amount_float,
                                data=data,
                                userid=userid,
                                kvb_key=kvb_key,
                                src_channel=src_channel,
                                username=username,
                                password=password,
                                log_file_name=log_file_name
                            )

                            if is_hold_success:
                                # =======
                                # Call I4C response API after hold
                                # =======
                                logger.info("[CALL_I4C_RESPONSE_API] Call I4C response API after hold")

                                # Convert balances to float safely
                                try:
                                    net_balance_float = float(decrypted_obj.get("NetBalance", 0.0))
                                except Exception:
                                    net_balance_float = 0.0

                                try:
                                    disputed_amount_float = float(disputed_amount)
                                except Exception:
                                    disputed_amount_float = 0.0

                                # ======= Condition for I4C "amount" =======
                                if net_balance_float <= 0:
                                    final_amount = 0.0
                                elif net_balance_float < disputed_amount_float:
                                    final_amount = net_balance_float
                                else:
                                    final_amount = disputed_amount_float

                                logger.info(f"[I4C_HOLD_AMOUNT] NetBalance={net_balance_float}, "
                                            f"DisputedAmount={disputed_amount_float}, "
                                            f"FinalAmount={final_amount}")

                                logger.info("[CALL_I4C_RESPONSE_API] Call I4C response API after hold")
                                # hold_amount = "{:.2f}".format(net_balance_float)
                                payload_data = data.get("request", {})
                                acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                                job_id = str(data.get("job_id", ""))
                                # CASA STMT response fields
                                pan_number = decrypted_obj.get("PAN", "") or "FORM60"
                                ifsc_code = decrypted_obj.get("IFSCCode", "")
                                net_balance = decrypted_obj.get("NetBalance", None)
                                # Get payer_account_number and rrn from i4c request
                                payer_account_number = ""
                                rrn = ""
                                rrn = incident.get("rrn", "")
                                instrument_data = payload_data.get("instrument", {})
                                payer_account_number = str(instrument_data.get("payer_account_number", ""))
                                # Use the same server timestamp for I4C response
                                transaction_datetime_val = hold_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                                i4c_payload = {
                                    "acknowledgement_no": acknowledgement_no,
                                    "job_id": job_id,
                                    "transactions": [
                                        {
                                            "txn_type": "Transaction Put on Hold",
                                            "txn_type_id": "1",
                                            "amount": final_amount,
                                            "transaction_datetime": transaction_datetime_val,
                                            "phone_number": phone_number,
                                            "email": email,
                                            "pan_number": pan_number,
                                            "ifsc_code": ifsc_code,
                                            "root_account_number": payer_account_number,
                                            "root_rrn_transaction_id": rrn,
                                            "root_bankid": "25",
                                            "status_code": "00",
                                            "root_effective_balance": str(net_balance),
                                            "root_ifsc_code": ifsc_code,
                                            "remarks": acknowledgement_no
                                        }
                                    ]
                                }
                                is_hold_i4c_success = call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'], log_file_name)

                                # db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                                # db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': 'success' if is_hold_i4c_success else 'failure', 'is_valid': True})

                        # =======
                        # Calculate pending amount
                        # =======
                        pending_amount_float = disputed_amount_float - (net_balance_float if net_balance_float >= 0.0 else 0.0)
                        logger.info(f"[AFTER_HOLD] Pending Amount: {pending_amount_float}")
                        
                        all_responses = [is_hold_i4c_success]

                        # =======
                        # Use the already matched transaction from RRN validation
                        # =======
                        if matched_casa_txn is not None:
                            logger.info(f"[CASA_MATCHED_TXN] Found transaction for RRN {rrn} at index {matched_index}: {matched_casa_txn}")
                            # =======
                            # Select transactions after the matched one until sum >= pending_amount_float
                            # =======
                            selected_txns = []
                            total_selected_amount = 0.0
                            if matched_index is not None:
                                for txn in casa_txn_details[matched_index+1:]:
                                    txn_desc = txn.get("TransactionDescription", "").upper()
                                    txn_amount_str = txn.get("TransactionAmount", "0")
                                    if txn.get("CodeDRCR") == "C":
                                        continue
                                    try:
                                        txn_amount = float(txn_amount_str)
                                    except Exception:
                                        txn_amount = 0.0

                                    # Simple disputed amount calculation
                                    disputed_amt = min(txn_amount, pending_amount_float - total_selected_amount)

                                    # Only select transactions based on description rules
                                    if any(x in txn_desc for x in ["NEFT", "RTGS", "IMPS"]) and txn_desc != "IMPS CHARGES":
                                        selected_txns.append(txn)
                                        #total_selected_amount += txn_amount
                                        logger.info(f"[CASA_SELECTED_TXN] Adding NEFT/RTGS/IMPS transaction: {txn} | Amount: {txn_amount} | Running Total: {total_selected_amount}")
                                        # Hit payment status inquiry API
                                        txn_desc_original = txn.get("TransactionDescription", "")
                                        txn_ref_number = ""
                                        match = re.search(r"-(\d+)-", txn_desc_original)
                                        if match:
                                            txn_ref_number = match.group(1)
                                        mode_of_payment = next((x for x in ["NEFT", "RTGS", "IMPS"] if x in txn_desc), "")
                                        split_txn_desc = txn_desc_original.split('-')
                                        txn_ref_number = split_txn_desc[1 if mode_of_payment in ['NEFT', 'IMPS'] else -1]

                                        casa_txn_date = txn.get("TransactionDate", "")
                                        try:
                                            casa_datetime_obj = datetime.strptime(casa_txn_date, "%d-%m-%Y %H:%M:%S")
                                            converted_datetime = casa_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                                        except Exception:
                                            converted_datetime = casa_txn_date
                                        amount_str = "{:.2f}".format(txn_amount)
                                        disputed_amt_str = "{:.2f}".format(disputed_amt)
                                        payer_account_number = instrument.get("payer_account_number", "")
                                        rrn = rrn = incident.get('rrn', '')
                                        is_success = money_transfer_to_non_upi(decrypted_obj, data, mode_of_payment, response_table, txn_ref_number, converted_datetime, amount_str, payer_account_number, disputed_amt_str, phone_number, email, rrn, log_file_name)
                                        total_selected_amount += txn_amount
                                        all_responses.append(is_success)
                                    elif "UPI" in txn_desc:
                                        selected_txns.append(txn)
                                        logger.info(f"[CASA_SELECTED_TXN] Adding UPI transaction: {txn} | Amount: {txn_amount} | Running Total: {total_selected_amount}")
                                        txn_amount_str = txn.get("TransactionAmount", "0")
                                        try:
                                            txn_amount = float(txn_amount_str)
                                        except Exception:
                                            txn_amount = 0.0
                                        # Extract ReferenceId (number between two hyphens in TransactionDescription)
                                        txn_desc_original = txn.get("TransactionDescription", "")
                                        reference_id = ""
                                        match = re.search(r"-(\d+)-", txn_desc_original)
                                        if match:
                                            reference_id = match.group(1)
                                        # Format TxnDate to 13-Jul-2025
                                        txn_date_str = txn.get("TransactionDate", "")
                                        txn_date_obj = datetime.strptime(txn_date_str, "%d-%m-%Y %H:%M:%S")
                                        txn_date_formatted = txn_date_obj.strftime("%d-%b-%Y")

                                        # Convert CASA datetime format from %d-%m-%Y to %Y-%m-%d
                                        casa_txn_date = txn.get("TransactionDate", "")
                                        try:
                                            casa_datetime_obj = datetime.strptime(casa_txn_date, "%d-%m-%Y %H:%M:%S")
                                            converted_datetime = casa_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                                        except Exception:
                                            converted_datetime = casa_txn_date

                                        payer_account_number = instrument.get("payer_account_number", "")

                                        rrn = rrn = incident.get('rrn', '')
                                        is_success = money_transfer_to_upi(decrypted_obj, data, reference_id, txn_date_formatted, txn_amount, disputed_amt, converted_datetime, payer_account_number, response_table, phone_number, email, rrn, log_file_name)
                                        total_selected_amount += txn_amount
                                        all_responses.append(is_success)
                                    elif any(x in txn_desc for x in ["ATM CSW", "POS/", "CHQ PAID", "AEPS"]):
                                        selected_txns.append(txn)
                                        txn_amount_str = txn.get("TransactionAmount", "0")
                                        try:
                                            txn_amount = float(txn_amount_str)
                                        except Exception:
                                            txn_amount = 0.0
                                        # Convert CASA datetime format from %d-%m-%Y to %Y-%m-%d
                                        casa_txn_date = txn.get("TransactionDate", "")
                                        try:
                                            casa_datetime_obj = datetime.strptime(casa_txn_date, "%d-%m-%Y %H:%M:%S")
                                            transaction_datetime_val = casa_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                                        except Exception:
                                            transaction_datetime_val = casa_txn_date
                                        #total_selected_amount += txn_amount
                                        logger.info(f"[CASA_SELECTED_TXN] Adding ATM/POS/CHQ PAID/AEPS transaction: {txn} | Amount: {txn_amount} | Running Total: {total_selected_amount}")
                                        payer_account_number = instrument.get("payer_account_number", "")
                                        curr_rrn = txn.get('ChequeNumber', '')
                                        is_success = non_money_transfer_to(decrypted_obj, data, payer_account_number, txn, curr_rrn, txn_desc, txn_amount, disputed_amt, response_table, transaction_datetime_val, phone_number, email, log_file_name)
                                        total_selected_amount += txn_amount
                                        all_responses.append(is_success)
                                    else:
                                        logger.info(f"[CASA_SKIPPED_TXN] Skipping transaction: {txn} | Description: {txn_desc}")
                                        continue
                                    if total_selected_amount >= pending_amount_float:
                                        break

                                db.bulk_update_record('i4c_request', {'job_id': data['job_id']}, {'status': 'P'})
                                incident_status = None
                                logger.info(f"[INCIDENT_RESPONSES] {json.dumps(all_responses)}")
                                if all(all_responses):
                                    incident_status = 'success'
                                else:
                                    if any(all_responses):
                                        incident_status = 'partial success'
                                    else:
                                        incident_status = 'failure'

                                db.bulk_update_record(incidents_table, {'job_id': data['job_id'], 'rrn': rrn}, {'status': incident_status, 'is_valid': True})
                            logger.info(f"[CASA_SELECTED_TXNS] Selected {len(selected_txns)} transactions after matched RRN, total amount: {total_selected_amount}, pending required: {pending_amount_float}")
                            logger.debug(f"[CASA_SELECTED_TXNS_DETAILS] {selected_txns}")
                        else:
                            logger.warning(f"[CASA_MATCHED_TXN] No transaction found for RRN {rrn}")
            else:
                logger.info("CASA STMT failed.")
