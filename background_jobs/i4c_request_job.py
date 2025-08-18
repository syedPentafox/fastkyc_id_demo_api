import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import os
from background_jobs.hold_funds_api import call_hold_funds_api
import re
from .i4c_response_api import call_i4c_response_api


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)



import json
from datetime import datetime
from utils.aes_encryption_decryption import AESUtil
from background_jobs.payment_status_inquiry_api import payment_status_inquiry_api
from background_jobs.upi_payment_status_inquiry_api import upi_payment_status_inquiry_api
from background_jobs.casa_stmt_api import casa_stmt_api
import uuid

from utils.db_connection import db

def i4c_request_job(request_json: str):
    data = request_json
    #logger.info(json.dumps(data, indent=4))
    logger.info('i4c_request_job request_json start')
    logger.info(data)
    logger.info('i4c_request_job request_json end')
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

    # db.create_record_('upi_fraud_transactions', {
    #     'job_id': data['job_id'],
    #     'sub_category': data['request']['sub_category'],
    #     'requestor': data['request']['instrument']['requestor'],
    #     'payer_bank_code': data['request']['instrument']['payer_bank_code'],
    #     'mode_of_payment': data['request']['instrument']['mode_of_payment'],
    #     'payer_mobile_number': data['request']['instrument']['payer_mobile_number'],
    #     'payer_account_number': data['request']['instrument']['payer_account_number'],
    #     'state': data['request']['instrument']['state'],
    #     'district': data['request']['instrument']['district'],
    #     'received_dt': data['received_dt'] 
    # })

    for idx, incident in enumerate(incidents):
            # db.create_record_('upi_fraud_incidents', {
            #     'ack_no': data['ack_no'],
            #     'job_id': data['job_id'],
            #     'amount': incident['amount'],
            #     'rrn': incident['rrn'],
            #     'transaction_date': incident['transaction_date'],
            #     'transaction_time': incident['transaction_time'],
            #     'disputed_amount': incident['disputed_amount'],
            #     'layer': incident['layer']
            # })
            
            # # Commit after creating transaction and all incidents
            # db.commit()

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
            #to_date = datetime.strptime(from_date_raw, "%Y-%m-%d").strftime("%d-%m-%Y") if from_date_raw else from_date_raw
            #if received_dt_raw:
            #    # received_dt example: "14-07-25 1:15:47.000000000 PM"
            #    try:
            #        # Split date and time, take first part
            #        date_part = str(received_dt_raw).split()[0]  # '14-07-25'
            #        # Convert 'yy-mm-dd' to 'dd-mm-yyyy'
            #        d, m, y = date_part.split('-')
            #        to_date = f"{d}-{m}-20{y}"
            #    except Exception as e:
            #        logger.warning(f"[CASA_STMT_PAYLOAD] Could not parse received_dt: {received_dt_raw}, error: {e}")
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
                userid
            )
            error_code = decrypted_obj.get("ErrorCode") if decrypted_obj is not None else None
            error_message = decrypted_obj.get("ErrorMessage") if decrypted_obj is not None else None


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
            #if payment_status_response is not None:
            #    ps_error_code = payment_status_response.get("ErrorCode")
            #    ps_error_message = payment_status_response.get("ErrorMessage")
            #    payment_status_success = (
            #         ps_error_code is not None and str(ps_error_code) == "0" and
            #         ps_error_message is not None and str(ps_error_message).lower() == "success"
            #     )

            # =======
            # If CASA API was successful, validate RRN before proceeding
            # =======
            if casa_stmt_success:
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
                    incident_datetime = datetime.strptime(incident_datetime_str, "%Y-%m-%d %H:%M:%S")
                except Exception as date_exc:
                    logger.warning(f"[RRN_VALIDATION] Could not parse incident datetime: {incident_datetime_str}, error: {date_exc}")
                
                # Search for matching transaction in CASA
                casa_txn_details = decrypted_obj.get("CasaTransactionDetails", [])
                rrn_valid = False
                matched_casa_txn = None
                matched_index = None
                
                logger.info(f"[RRN_VALIDATION] Validating RRN: {rrn}, Amount: {incident_amount}, DateTime: {incident_datetime}")
                
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
                                        logger.info(f"[RRN_VALIDATION] Valid RRN found - RRN: {rrn}, Amount: {casa_amount}, Date: {casa_datetime.date()}")
                                        break
                                    else:
                                        logger.info(f"[RRN_VALIDATION] RRN and amount match but date mismatch - Casa: {casa_datetime.date()}, Incident: {incident_datetime.date()}")
                                except Exception as casa_date_exc:
                                    logger.warning(f"[RRN_VALIDATION] Could not parse CASA datetime: {txn_date_str}, error: {casa_date_exc}")
                            else:
                                logger.info(f"[RRN_VALIDATION] RRN match but amount mismatch - Casa: {casa_amount}, Incident: {incident_amount_float}")
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
                    
                    # Use current timestamp for invalid RRN
                    current_timestamp = datetime.now()
                    transaction_datetime_val = current_timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    amount = "{:.2f}".format(disputed_amount_float)
                    
                    invalid_rrn_payload = {
                        "acknowledgement_no": acknowledgement_no,
                        "job_id": job_id,
                        "transactions": [
                            {
                                "txn_type": "Transaction Put on Hold",
                                "txn_type_id": "1",
                                "amount": amount,
                                "transaction_datetime": transaction_datetime_val,
                                "phone_number": "1234567890",
                                "email": "testing@gmail.com",
                                "pan_number": pan_number,
                                "ifsc_code": ifsc_code,
                                "root_account_number": payer_account_number,
                                "root_rrn_transaction_id": rrn,
                                "root_bankid": "25",
                                "status_code": "02",
                                "root_effective_balance": str(net_balance),
                                "root_ifsc_code": ifsc_code,
                                "remarks": acknowledgement_no
                            }
                        ]
                    }
                    
                    call_i4c_response_api(invalid_rrn_payload, kvb_key, kvb_endpoint)
                    logger.info(f"[RRN_VALIDATION] Sent status code 02 response for invalid RRN: {rrn}")
                    
                    # Skip balance logic for this incident
                    continue
                
                logger.info(f"[RRN_VALIDATION] RRN validation passed for: {rrn}")
                
                mode_of_payment = instrument.get("mode_of_payment", "CREDIT").upper()
                transaction_type = instrument.get("transaction_type", "").upper()
                if mode_of_payment == "DEBIT" and transaction_type in ["IMPS", "NEFT", "RTGS", "UPI", "ATM", "POS", "CHQ PAID", "AEPS"]:
                    # For DEBIT, directly call payment inquiry API and then I4C response API
                    payment_status_response = None
                    try:
                        if transaction_type in ["IMPS", "NEFT", "RTGS"]:
                            # Prepare payment inquiry payload
                            txn_ref_number = instrument.get("transaction_ref_number", "")
                            payment_status_dict = {
                                "Transaction_Ref_Number": txn_ref_number,
                                "Mode_Of_Payment": transaction_type
                            }
                            payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")
                            payment_status_response = payment_status_inquiry_api(
                                payment_status_dict,
                                kvb_key,
                                payment_status_url,
                                src_channel,
                                username,
                                password
                            )
                            logger.info(f"[PAYMENT_STATUS_INQUIRY_DEBIT] Response: {payment_status_response}")
                            payee_account_number = payment_status_response.get("Beneficiary_Account_No", "") if payment_status_response else ""
                            i4c_payload = {
                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                "job_id": data.get("job_id", ""),
                                "transactions": [
                                    {
                                        "txn_type": "Money Transfer To",
                                        "txn_type_id": "3",
                                        "amount": str(instrument.get("disputed_amount", "")),
                                        "transaction_datetime": incident.get("transaction_date", "") + " " + incident.get("transaction_time", ""),
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                        "ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "root_account_number": instrument.get("payer_account_number", ""),
                                        "root_rrn_transaction_id": incident.get("rrn", ""),
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "remarks": data.get("request", {}).get("acknowledgement_no", ""),
                                        "payee_bank": "KVB",
                                        "payee_bank_code": "25",
                                        "payee_account_number": payee_account_number
                                    }
                                ]
                            }
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                        elif transaction_type == "UPI":
                            upi_payment_status_path = os.getenv("UPI_PAYMENT_STATUS_INQUIRY_PATH", "/ESB/UPITransactionEnquiry")
                            upi_payment_status_url = kvb_endpoint.rstrip("/") + "/" + upi_payment_status_path.lstrip("/")
                            reference_id = instrument.get("reference_id", "")
                            txn_date_str = instrument.get("transaction_date", "")
                            txn_date_formatted = ""
                            try:
                                date_part = txn_date_str.split()[0] if txn_date_str else ""
                                if date_part:
                                    day, month, year = date_part.split('-')
                                    import calendar
                                    month_name = calendar.month_abbr[int(month)]
                                    txn_date_formatted = f"{int(day)}-{month_name}-{year}"
                            except Exception as date_exc:
                                logger.warning(f"[UPI_TXN_DATE_FORMAT] Could not format txn date: {txn_date_str}, error: {date_exc}")
                            upi_payload = {
                                "ReferenceId": reference_id,
                                "TxnDate": txn_date_formatted
                            }
                            upi_response = upi_payment_status_inquiry_api(
                                upi_payload,
                                kvb_key,
                                upi_payment_status_url,
                                src_channel,
                                username,
                                password
                            )
                            logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_DEBIT] Response: {upi_response}")
                            rrn = upi_response.get("TransactionId", "") if upi_response else ""
                            rrn = incident.get("rrn", "")
                            payee_account_number = upi_response.get("PayeeAccountNumber", "") if upi_response else ""
                            upi_amount = upi_response.get("Amount", "") if upi_response else ""
                            i4c_payload = {
                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                "job_id": data.get("job_id", ""),
                                "transactions": [
                                    {
                                        "txn_type": "Money Transfer To",
                                        "txn_type_id": "3",
                                        "rrn": rrn,
                                        "payee_bank": "KVB",
                                        "payee_bank_code": "25",
                                        "payee_account_number": payee_account_number,
                                        "amount": str(instrument.get("disputed_amount", "")),
                                        "transaction_datetime": incident.get("transaction_date", "") + " " + incident.get("transaction_time", ""),
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                        "disputed_amount": str(instrument.get("disputed_amount", "")),
                                        "ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "root_account_number": instrument.get("payer_account_number", ""),
                                        "root_rrn_transaction_id": rrn,
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "remarks": data.get("request", {}).get("acknowledgement_no", ""),
                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", "")
                                    }
                                ]
                            }
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                        elif transaction_type == "ATM":
                            # For DEBIT ATM, directly call I4C response API without inquiry
                            atm_id = instrument.get("atm_id", "")
                            place_of_atm = instrument.get("place_of_atm", "")
                            atm_of_bank = instrument.get("atm_of_bank", "")
                            
                            i4c_payload = {
                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                "job_id": data.get("job_id", ""),
                                "transactions": [
                                    {
                                        "txn_type": "Withdrawal through ATM",
                                        "txn_type_id": "5",
                                        "amount": str(instrument.get("disputed_amount", "")),
                                        "transaction_datetime": incident.get("transaction_date", "") + " " + incident.get("transaction_time", ""),
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                        "disputed_amount": str(instrument.get("disputed_amount", "")),
                                        "atm_id": atm_id,
                                        "place_of_atm": place_of_atm,
                                        "atm_of_bank": atm_of_bank,
                                        "root_account_number": instrument.get("payer_account_number", ""),
                                        "root_rrn_transaction_id": instrument.get("rrn", ""),
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "remarks": data.get("request", {}).get("acknowledgement_no", "")
                                    }
                                ]
                            }
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                        elif transaction_type == "POS":
                            # For DEBIT POS, directly call I4C response API without inquiry
                            mid = instrument.get("mid", "")
                            tid = instrument.get("tid", "")
                            approval_code = instrument.get("approval_code", "")
                            merchant_name = instrument.get("merchant_name", "")
                            pos_transaction_id = instrument.get("pos_transaction_id", "")
                            
                            i4c_payload = {
                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                "job_id": data.get("job_id", ""),
                                "transactions": [
                                    {
                                        "txn_type": "Withdrawal through POS",
                                        "txn_type_id": "11",
                                        "amount": str(instrument.get("disputed_amount", "")),
                                        "transaction_datetime": incident.get("transaction_date", "") + " " + incident.get("transaction_time", ""),
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                        "disputed_amount": str(instrument.get("disputed_amount", "")),
                                        "mid": mid,
                                        "tid": tid,
                                        "approval_code": approval_code,
                                        "merchant_name": merchant_name,
                                        "Pos_transaction_id": pos_transaction_id,
                                        "root_account_number": instrument.get("payer_account_number", ""),
                                        "root_rrn_transaction_id": instrument.get("rrn", ""),
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "remarks": data.get("request", {}).get("acknowledgement_no", "")
                                    }
                                ]
                            }
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                        elif transaction_type == "CHQ PAID":
                            # For DEBIT CHQ PAID, directly call I4C response API without inquiry
                            cheque_no = instrument.get("cheque_no", "")
                            withdrawal_date = instrument.get("transaction_date", "")
                            location = instrument.get("location", "")
                            managername = instrument.get("managername", "Abc")
                            managernumber = instrument.get("managernumber", "9876543210")
                            
                            i4c_payload = {
                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                "job_id": data.get("job_id", ""),
                                "transactions": [
                                    {
                                        "txn_type": "Withdrawal through Cheque",
                                        "txn_type_id": "14",
                                        "account_number": instrument.get("payer_account_number", ""),
                                        "ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "cheque_no": cheque_no,
                                        "withdrawal_date": withdrawal_date,
                                        "amount": str(instrument.get("disputed_amount", "")),
                                        "disputed_amount": str(instrument.get("disputed_amount", "")),
                                        "location": location,
                                        "managername": managername,
                                        "managernumber": managernumber,
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                        "root_account_number": instrument.get("payer_account_number", ""),
                                        "root_rrn_transaction_id": instrument.get("rrn", ""),
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "remarks": data.get("request", {}).get("acknowledgement_no", "")
                                    }
                                ]
                            }
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                        elif transaction_type == "AEPS":
                            # For DEBIT AEPS, directly call I4C response API without inquiry
                            rrn_val = instrument.get("rrn", "")
                            
                            i4c_payload = {
                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                "job_id": data.get("job_id", ""),
                                "transactions": [
                                    {
                                        "txn_type": "Withdrawal through AEPS",
                                        "txn_type_id": "6",
                                        "rrn": rrn_val,
                                        "amount": str(instrument.get("disputed_amount", "")),
                                        "disputed_amount": str(instrument.get("disputed_amount", "")),
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                        "root_account_number": instrument.get("payer_account_number", ""),
                                        "root_rrn_transaction_id": instrument.get("rrn", ""),
                                        "root_bankid": "25",
                                        "status_code": "00",
                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                        "remarks": data.get("request", {}).get("acknowledgement_no", "")
                                    }
                                ]
                            }
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
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
                        logger.info(f"[KVB_HOLD] NetBalance ({net_balance_float}) > DisputedAmount ({disputed_amount}): hold disputed amount")
                        
                        # Call hold funds API and capture the timestamp it used
                        hold_timestamp = call_hold_funds_api(
                            kvb_endpoint=kvb_endpoint,
                            hold_fund_path=hold_fund_path,
                            disputed_amount=disputed_amount_float,
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
                                    "phone_number": "1234567890",
                                    "email": "testing@gmail.com",
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
                        call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                    else:
                        if net_balance_float <= 0:
                            # =======
                            # Cannot hold any amount or call I4C response API if net balance is negative
                            # =======
                            logger.warning(f"[KVB_NEGATIVE_BALANCE] NetBalance ({net_balance_float}) is negative. Cannot hold or call I4C response API.")
                            pending_amount_float = disputed_amount_float
                            logger.info(f"[AFTER_HOLD] Pending Amount: {pending_amount_float}")
                        else:
                            # =======
                            # Hold Net Balance only
                            # =======
                            logger.info(f"[KVB_CANT_HOLD] NetBalance ({net_balance_float}) <= DisputedAmount ({disputed_amount}): can't hold disputed amount")
                            logger.info(f"[KVB_CANT_HOLD] Holding {net_balance_float} Net Balance only")
                            
                            # Call hold funds API and capture the timestamp it used
                            hold_timestamp = call_hold_funds_api(
                                kvb_endpoint=kvb_endpoint,
                                hold_fund_path=hold_fund_path,
                                disputed_amount=net_balance_float,
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
                            hold_amount = "{:.2f}".format(net_balance_float)
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
                                        "amount": hold_amount,
                                        "transaction_datetime": transaction_datetime_val,
                                        "phone_number": "1234567890",
                                        "email": "testing@gmail.com",
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
                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)

                            # =======
                            # Calculate pending amount
                            # =======
                            pending_amount_float = disputed_amount_float - net_balance_float
                            logger.info(f"[AFTER_HOLD] Pending Amount: {pending_amount_float}")

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
                                    if any(x in txn_desc for x in ["NEFT", "RTGS", "IMPS"]):
                                        selected_txns.append(txn)
                                        total_selected_amount += txn_amount
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
                                        payment_status_dict = {
                                            "Transaction_Ref_Number": txn_ref_number,
                                            "Mode_Of_Payment": mode_of_payment
                                        }
                                        payment_status_response = None
                                        try:
                                            payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")
                                            payment_status_response = payment_status_inquiry_api(
                                                payment_status_dict,
                                                kvb_key,
                                                payment_status_url,
                                                src_channel,
                                                username,
                                                password
                                            )
                                            logger.info(f"[PAYMENT_STATUS_INQUIRY] Response for txn {txn.get('ChequeNumber', '')}: {payment_status_response}")
                                            # Hit I4C response API with required payload only after successful payment status inquiry
                                            payee_bank = "KVB"
                                            payee_bank_code = "25"
                                            payee_account_number = ""
                                            if payment_status_response and isinstance(payment_status_response, dict):
                                                payee_account_number = payment_status_response.get("Beneficiary_Account_No", "")
                                            
                                            # Convert CASA datetime format from %d-%m-%Y to %Y-%m-%d
                                            casa_txn_date = txn.get("TransactionDate", "")
                                            try:
                                                casa_datetime_obj = datetime.strptime(casa_txn_date, "%d-%m-%Y %H:%M:%S")
                                                converted_datetime = casa_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                                            except Exception:
                                                converted_datetime = casa_txn_date
                                            
                                            i4c_payload = {
                                                "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                                "job_id": data.get("job_id", ""),
                                                "transactions": [
                                                    {
                                                        "txn_type": "Money Transfer To",
                                                        "txn_type_id": "3",
                                                        "amount": str(txn_amount),
                                                        "disputed_amount": str(disputed_amt),
                                                        "transaction_datetime": converted_datetime,
                                                        "phone_number": "1234567890",
                                                        "email": "testing@gmail.com",
                                                        "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                                        "ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                                        "root_account_number": instrument.get("payer_account_number", ""),
                                                        "root_rrn_transaction_id": rrn,
                                                        "root_bankid": payee_bank_code,
                                                        "status_code": "00",
                                                        "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                                        "root_ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                                        "remarks": data.get("request", {}).get("acknowledgement_no", ""),
                                                        "payee_bank": payee_bank,
                                                        "payee_bank_code": payee_bank_code,
                                                        "payee_account_number": payee_account_number
                                                    }
                                                ]
                                            }
                                            call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                                            logger.info(f"[I4C_RESPONSE_API] Called for txn {txn.get('ChequeNumber', '')} amount {txn_amount}")
                                        except Exception as psi_exc:
                                            logger.error(f"[PAYMENT_STATUS_INQUIRY_ERROR] {psi_exc}")
                                    elif "UPI" in txn_desc:
                                        selected_txns.append(txn)
                                        txn_amount_str = txn.get("TransactionAmount", "0")
                                        try:
                                            txn_amount = float(txn_amount_str)
                                        except Exception:
                                            txn_amount = 0.0
                                        total_selected_amount += txn_amount
                                        logger.info(f"[CASA_SELECTED_TXN] Adding UPI transaction: {txn} | Amount: {txn_amount} | Running Total: {total_selected_amount}")
                                        # Hit UPI payment status inquiry API and then I4C response API for this transaction
                                        try:
                                            upi_payment_status_path = os.getenv("UPI_PAYMENT_STATUS_INQUIRY_PATH", "/ESB/UPITransactionEnquiry")
                                            upi_payment_status_url = kvb_endpoint.rstrip("/") + "/" + upi_payment_status_path.lstrip("/")
                                            # Extract ReferenceId (number between two hyphens in TransactionDescription)
                                            txn_desc_original = txn.get("TransactionDescription", "")
                                            reference_id = ""
                                            match = re.search(r"-(\d+)-", txn_desc_original)
                                            if match:
                                                reference_id = match.group(1)
                                            # Format TxnDate to 13-Jul-2025
                                            txn_date_str = txn.get("TransactionDate", "")
                                            txn_date_formatted = ""
                                            try:
                                                date_part = txn_date_str.split()[0] if txn_date_str else ""
                                                if date_part:
                                                    day, month, year = date_part.split('-')
                                                    import calendar
                                                    month_name = calendar.month_abbr[int(month)]
                                                    txn_date_formatted = f"{int(day)}-{month_name}-{year}"
                                            except Exception as date_exc:
                                                logger.warning(f"[UPI_TXN_DATE_FORMAT] Could not format txn date: {txn_date_str}, error: {date_exc}")
                                            upi_payload = {
                                                "ReferenceId": reference_id,
                                                "TxnDate": txn_date_formatted
                                            }
                                            logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY] Payload for txn {reference_id}: {upi_payload}")
                                            upi_response = upi_payment_status_inquiry_api(
                                                upi_payload,
                                                kvb_key,
                                                upi_payment_status_url,
                                                src_channel,
                                                username,
                                                password
                                            )
                                            logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY] Response for txn {reference_id}: {upi_response}")
                                            # Hit I4C response API with required payload only after successful UPI inquiry
                                            try:
                                                rrn = upi_response.get("TransactionId", "") if upi_response else ""
                                                rrn = incident.get("rrn", "")
                                                payee_account_number = upi_response.get("PayeeAccountNumber", "") if upi_response else ""
                                                upi_amount = upi_response.get("Amount", "") if upi_response else ""
                                                
                                                # Convert CASA datetime format from %d-%m-%Y to %Y-%m-%d
                                                casa_txn_date = txn.get("TransactionDate", "")
                                                try:
                                                    casa_datetime_obj = datetime.strptime(casa_txn_date, "%d-%m-%Y %H:%M:%S")
                                                    converted_datetime = casa_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                                                except Exception:
                                                    converted_datetime = casa_txn_date
                                                
                                                i4c_payload = {
                                                    "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
                                                    "job_id": data.get("job_id", ""),
                                                    "transactions": [
                                                        {
                                                            "txn_type": "Money Transfer To",
                                                            "txn_type_id": "3",
                                                            "rrn": rrn,
                                                            "payee_bank": "KVB",
                                                            "payee_bank_code": "25",
                                                            "payee_account_number": payee_account_number,
                                                            "amount": str(txn_amount),
                                                            "disputed_amount": str(disputed_amt),
                                                            "transaction_datetime": converted_datetime,
                                                            "phone_number": "1234567890",
                                                            "email": "testing@gmail.com",
                                                            "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                                                            "ifsc_code": decrypted_obj.get("IFSCCode", ""),
                                                            "root_account_number": instrument.get("payer_account_number", ""),
                                                            "root_rrn_transaction_id": rrn,
                                                            "root_bankid": "25",
                                                            "status_code": "00",
                                                            "remarks": data.get("request", {}).get("acknowledgement_no", ""),
                                                            "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                                                            "root_ifsc_code": decrypted_obj.get("IFSCCode", "")
                                                        }
                                                    ]
                                                }
                                                call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                                                logger.info(f"[I4C_RESPONSE_API] Called for UPI txn {reference_id} amount {upi_amount}")
                                            except Exception as i4c_exc:
                                                logger.error(f"[I4C_RESPONSE_API_ERROR] {i4c_exc}")
                                        except Exception as upi_exc:
                                            logger.error(f"[UPI_PAYMENT_STATUS_INQUIRY_ERROR] {upi_exc}")
                                    elif any(x in txn_desc for x in ["ATM CSW", "POS", "CHQ PAID", "AEPS"]):
                                        selected_txns.append(txn)
                                        total_selected_amount += txn_amount
                                        logger.info(f"[CASA_SELECTED_TXN] Adding ATM/POS/CHQ PAID/AEPS transaction: {txn} | Amount: {txn_amount} | Running Total: {total_selected_amount}")
                                        try:
                                            payload_data = data.get("request", {})
                                            acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
                                            job_id = str(data.get("job_id", ""))
                                            pan_number = decrypted_obj.get("PAN", "") or "FORM60"
                                            ifsc_code = decrypted_obj.get("IFSCCode", "")
                                            net_balance = decrypted_obj.get("NetBalance", None)
                                            payer_account_number = instrument.get("payer_account_number", "")
                                            # Convert CASA datetime format from %d-%m-%Y to %Y-%m-%d
                                            casa_txn_date = txn.get("TransactionDate", "")
                                            try:
                                                casa_datetime_obj = datetime.strptime(casa_txn_date, "%d-%m-%Y %H:%M:%S")
                                                transaction_datetime_val = casa_datetime_obj.strftime("%Y-%m-%d %H:%M:%S")
                                            except Exception:
                                                transaction_datetime_val = casa_txn_date
                                            rrn = incident.get("rrn", "")
                                            root_rrn_transaction_id = rrn
                                            root_bankid = "25"
                                            status_code = "00"
                                            remarks = acknowledgement_no
                                            root_effective_balance = str(decrypted_obj.get("NetBalance", ""))
                                            root_ifsc_code = decrypted_obj.get("IFSCCode", "")
                                            phone_number = "1234567890"
                                            email = "testing@gmail.com"
                                            # ATM
                                            if "ATM CSW" in txn_desc:
                                                # Parse ATM fields
                                                # Example: ATM CSW/0120068848/SIVANANATHA COLON/COIMBAT
                                                atm_id = ""
                                                place_of_atm = ""
                                                atm_of_bank = ""
                                                desc_parts = txn.get("TransactionDescription", "").split("/")
                                                if len(desc_parts) >= 3:
                                                    atm_id = desc_parts[1].strip()
                                                    place_of_atm = desc_parts[2].strip()
                                                i4c_payload = {
                                                    "acknowledgement_no": acknowledgement_no,
                                                    "Job_id": job_id,
                                                    "transactions": [
                                                        {
                                                            "txn_type": "Withdrawal through ATM",
                                                            "txn_type_id": "5",
                                                            "amount": str(txn_amount),
                                                            "disputed_amount": str(disputed_amt),
                                                            "transaction_datetime": transaction_datetime_val,
                                                            "phone_number": phone_number,
                                                            "email": email,
                                                            "pan_number": pan_number,
                                                            "atm_id": atm_id,
                                                            "place_of_atm": place_of_atm,
                                                            "atm_of_bank": atm_of_bank,
                                                            "root_account_number": payer_account_number,
                                                            "root_rrn_transaction_id": root_rrn_transaction_id,
                                                            "root_bankid": root_bankid,
                                                            "status_code": status_code,
                                                            "remarks": remarks,
                                                            "root_effective_balance": root_effective_balance,
                                                            "root_ifsc_code": root_ifsc_code
                                                        }
                                                    ]
                                                }
                                            # POS
                                            elif "POS" in txn_desc:
                                                # Example: POS/123456/MID123/TID456/APPROVAL789/MERCHANT/NAME/POSID
                                                mid = txn.get("MID", "")
                                                tid = txn.get("TID", "")
                                                approval_code = txn.get("ApprovalCode", "")
                                                merchant_name = txn.get("MerchantName", "")
                                                pos_transaction_id = txn.get("PosTransactionId", "")
                                                i4c_payload = {
                                                    "acknowledgement_no": acknowledgement_no,
                                                    "Job_id": job_id,
                                                    "transactions": [
                                                        {
                                                            "txn_type": "Withdrawal through POS",
                                                            "txn_type_id": "11",
                                                            "amount": str(txn_amount),
                                                            "disputed_amount": str(disputed_amt),
                                                            "transaction_datetime": transaction_datetime_val,
                                                            "phone_number": phone_number,
                                                            "email": email,
                                                            "pan_number": pan_number,
                                                            "mid": mid,
                                                            "tid": tid,
                                                            "approval_code": approval_code,
                                                            "merchant_name": merchant_name,
                                                            "Pos_transaction_id": pos_transaction_id,
                                                            "root_account_number": payer_account_number,
                                                            "root_rrn_transaction_id": root_rrn_transaction_id,
                                                            "root_bankid": root_bankid,
                                                            "status_code": status_code,
                                                            "remarks": remarks,
                                                            "root_effective_balance": root_effective_balance,
                                                            "root_ifsc_code": root_ifsc_code
                                                        }
                                                    ]
                                                }
                                            # CHQ PAID
                                            elif "CHQ PAID" in txn_desc:
                                                cheque_no = txn.get("ChequeNumber", "")
                                                withdrawal_date = txn.get("TransactionDate", "")
                                                location = txn.get("BranchCode", "")
                                                managername = "Abc"
                                                managernumber = "9876543210"
                                                i4c_payload = {
                                                    "acknowledgement_no": acknowledgement_no,
                                                    "Job_id": job_id,
                                                    "transactions": [
                                                        {
                                                            "txn_type": "Withdrawal through Cheque",
                                                            "txn_type_id": "14",
                                                            "account_number": payer_account_number,
                                                            "ifsc_code": ifsc_code,
                                                            "cheque_no": cheque_no,
                                                            "withdrawal_date": withdrawal_date,
                                                            "amount": str(txn_amount),
                                                            "disputed_amount": str(disputed_amt),
                                                            "location": location,
                                                            "managername": managername,
                                                            "managernumber": managernumber,
                                                            "phone_number": phone_number,
                                                            "email": email,
                                                            "pan_number": pan_number,
                                                            "root_account_number": payer_account_number,
                                                            "root_rrn_transaction_id": root_rrn_transaction_id,
                                                            "root_bankid": root_bankid,
                                                            "status_code": status_code,
                                                            "remarks": remarks,
                                                            "root_effective_balance": root_effective_balance,
                                                            "root_ifsc_code": root_ifsc_code
                                                        }
                                                    ]
                                                }
                                            # AEPS
                                            elif "AEPS" in txn_desc:
                                                # Example: AEPS ACQ CW-99506997-KVB-11:15 AM-RRN:424711036020-1 112, ...
                                                rrn_val = ""
                                                match = re.search(r"RRN:([\w\d]+)", txn.get("TransactionDescription", ""))
                                                if match:
                                                    rrn_val = match.group(1)
                                                i4c_payload = {
                                                    "acknowledgement_no": acknowledgement_no,
                                                    "Job_id": job_id,
                                                    "transactions": [
                                                        {
                                                            "txn_type": "Withdrawal through AEPS",
                                                            "txn_type_id": "6",
                                                            "rrn": rrn_val,
                                                            "amount": str(txn_amount),
                                                            "disputed_amount": str(disputed_amt),
                                                            "phone_number": phone_number,
                                                            "email": email,
                                                            "pan_number": pan_number,
                                                            "root_account_number": payer_account_number,
                                                            "root_rrn_transaction_id": root_rrn_transaction_id,
                                                            "root_bankid": root_bankid,
                                                            "status_code": status_code,
                                                            "remarks": remarks,
                                                            "root_effective_balance": root_effective_balance,
                                                            "root_ifsc_code": root_ifsc_code
                                                        }
                                                    ]
                                                }
                                            else:
                                                i4c_payload = None
                                            if i4c_payload:
                                                call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint)
                                                logger.info(f"[I4C_RESPONSE_API] Called for {txn_desc} txn: {txn}")
                                        except Exception as i4c_exc:
                                            logger.error(f"[I4C_RESPONSE_API_ERROR] {i4c_exc}")
                                    else:
                                        logger.info(f"[CASA_SKIPPED_TXN] Skipping transaction: {txn} | Description: {txn_desc}")
                                        continue
                                    if total_selected_amount >= pending_amount_float:
                                        break
                            logger.info(f"[CASA_SELECTED_TXNS] Selected {len(selected_txns)} transactions after matched RRN, total amount: {total_selected_amount}, pending required: {pending_amount_float}")
                            logger.debug(f"[CASA_SELECTED_TXNS_DETAILS] {selected_txns}")
                        else:
                            logger.warning(f"[CASA_MATCHED_TXN] No transaction found for RRN {rrn}")
            else:
                logger.info("CASA STMT failed.")
