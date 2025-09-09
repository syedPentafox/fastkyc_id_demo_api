import os
import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import re
from datetime import datetime
import os
import logging
import re
from utils.db_connection import db
from orm_model.core_models import BankMaster, BranchManagerDetails
from background_jobs.payment_status_inquiry_api import payment_status_inquiry_api
from background_jobs.upi_payment_status_inquiry_api import upi_payment_status_inquiry_api
from background_jobs.i4c_response_api import call_i4c_response_api


def sanitize_account_number(account_no: str) -> str:
    if not account_no:
        return ""
    return re.sub(r"\D", "", account_no)

def get_branch_manager(db, branch_code: str):
    if not branch_code:
        return None
    session = db.get_db_session()
    return (
        session.query(BranchManagerDetails)
        .filter(BranchManagerDetails.branch_code == branch_code)
        .first()
    )
def get_bank_details_by_ifsc(db, ifsc_code: str):
    if not ifsc_code:
        return None
    session = db.get_db_session()
    prefix = ifsc_code[:4].upper().strip()
    return session.query(BankMaster).filter(
        BankMaster.ifsc_code.like(f"{prefix}%")
    ).first()


def resolve_payee_bank(db, ifsc_code: str):
    bank_record = get_bank_details_by_ifsc(db, ifsc_code)
    if bank_record:
        return bank_record.bank_name, str(bank_record.bank_code)
    return "KVB", "25"



def money_transfer_to_non_upi(decrypted_obj, data, rrn,transaction_type, response_table, ack_rrn, transaction_datetime,
                              amount, root_account_number, disputed_amount, phone_number, email,
                              log_file_name):
    logger = logging.getLogger(log_file_name)
    kvb_endpoint = os.getenv("KVB_ENDPOINT", "")
    payment_status_path = os.getenv("PAYMENT_STATUS_INQUIRY_PATH", "/ESB/PaymentStatusInquiry")
    kvb_key = os.getenv("KVB_KEY_VALUE")
    src_channel = os.getenv("KVB_SRC_CHANNEL")
    username = os.getenv("KVB_USERNAME")
    password = os.getenv("KVB_PASSWORD")

    payment_status_dict = {
        "Transaction_Ref_Number": rrn,
        "Mode_Of_Payment": transaction_type
    }
    payment_status_url = kvb_endpoint.rstrip("/") + "/" + payment_status_path.lstrip("/")
    payment_status_response = payment_status_inquiry_api(
        payment_status_dict,
        kvb_key,
        payment_status_url,
        src_channel,
        username,
        password,
        log_file_name
    )
    logger.info(f"[PAYMENT_STATUS_INQUIRY] Response: {payment_status_response}")

    txn_id = ""
    payee_account_number = ""
    ifsc_code = ""
    payee_account_number = root_account_number
    ifsc_code = decrypted_obj.get("IFSCCode", "") or ""
    txn_id = rrn
    if payment_status_response and isinstance(payment_status_response, dict):
        payee_account_number = payment_status_response.get("Beneficiary_Account_No", "") if payment_status_response else root_account_number
        ifsc_code = payment_status_response.get("IFSC", "") or ""
        txn_id = payment_status_response.get("TxnId", "") if payment_status_response else rrn

    if not payee_account_number:
        payee_account_number = root_account_number
        ifsc_code = decrypted_obj.get("IFSCCode", "") or ""
        txn_id = rrn

    payee_account_number = sanitize_account_number(payee_account_number)
    payee_bank, payee_bank_code = resolve_payee_bank(db, ifsc_code)

    i4c_payload = {
        "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
        "job_id": data.get("job_id", ""),
        "transactions": [
            {
                "txn_type": "Money Transfer To",
                "txn_type_id": "3",
                "amount": str(amount),
                "disputed_amount": str(disputed_amount),
                "transaction_datetime": transaction_datetime,
                "phone_number": phone_number,
                "email": email,
                "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                "ifsc_code": ifsc_code,
                "root_account_number": root_account_number,
                "root_rrn_transaction_id": ack_rrn,
                "rrn_transaction_id": txn_id,
                "root_bankid": "25",
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
    return call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data["received_dt"], log_file_name)


def money_transfer_to_upi(decrypted_obj, data,rrn,txn_date_formatted, amount, disputed_amount,
                          transaction_datetime, payer_account_number, response_table, phone_number,
                          email, root_rrn, log_file_name):
    logger = logging.getLogger(log_file_name)
    kvb_endpoint = os.getenv("KVB_ENDPOINT", "")
    upi_payment_status_path = os.getenv("UPI_PAYMENT_STATUS_INQUIRY_PATH", "/ESB/UPITransactionEnquiry")
    upi_payment_status_url = kvb_endpoint.rstrip("/") + "/" + upi_payment_status_path.lstrip("/")
    kvb_key = os.getenv("KVB_KEY_VALUE")
    src_channel = os.getenv("KVB_SRC_CHANNEL")
    username = os.getenv("KVB_USERNAME")
    password = os.getenv("KVB_PASSWORD")

    upi_payload = {
        "ReferenceId": rrn,
        "TxnDate": txn_date_formatted
    }
    upi_response = upi_payment_status_inquiry_api(
        upi_payload,
        kvb_key,
        upi_payment_status_url,
        src_channel,
        username,
        password,
        log_file_name
    )
    logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_DEBIT] Response: {upi_response}")

    txn_id = ""
    payee_account_number = payer_account_number
    ifsc_code = decrypted_obj.get("IFSCCode", "") or ""
    if upi_response and isinstance(upi_response, dict):
        payee_account_number = upi_response.get("PayeeAccountNumber", "") or payee_account_number
        ifsc_code = upi_response.get("IFSC", "") or ifsc_code
        txn_id = upi_response.get("TransactionId", "") if upi_response else "root_rrn"

    payee_account_number = sanitize_account_number(payee_account_number)
    txn_id=sanitize_account_number(txn_id)
    payee_bank, payee_bank_code = resolve_payee_bank(db, ifsc_code)

    i4c_payload = {
        "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
        "job_id": data.get("job_id", ""),
        "transactions": [
            {
                "txn_type": "Money Transfer To",
                "txn_type_id": "3",
                "rrn_transaction_id": txn_id,
                "payee_bank": payee_bank,
                "payee_bank_code": payee_bank_code,
                "payee_account_number": payee_account_number,
                "amount": str(amount),
                "transaction_datetime": transaction_datetime,
                "phone_number": phone_number,
                "email": email,
                "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
                "disputed_amount": str(disputed_amount),
                "ifsc_code": ifsc_code,
                "root_account_number": payer_account_number,
                "root_rrn_transaction_id": root_rrn,
                "root_bankid": "25",
                "status_code": "00",
                "remarks": data.get("request", {}).get("acknowledgement_no", ""),
                "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
                "root_ifsc_code": decrypted_obj.get("IFSCCode", "")
            }
        ]
    }
    return call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data["received_dt"], log_file_name)

def non_money_transfer_to(ack_rrn,decrypted_obj, data, payer_account_number, txn, rrn, txn_desc, txn_amount, disputed_amt, response_table, transaction_datetime, phone_number, email, log_file_name):
    logger = logging.getLogger(log_file_name)
    kvb_key = os.getenv("KVB_KEY_VALUE")
    kvb_endpoint = os.getenv("KVB_ENDPOINT", "")

    payload_data = data.get("request", {})
    acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
    job_id = str(data.get("job_id", ""))
    pan_number = decrypted_obj.get("PAN", "") or "FORM60"
    ifsc_code = decrypted_obj.get("IFSCCode", "")
    net_balance = decrypted_obj.get("NetBalance", None)
    
    root_rrn_transaction_id = ack_rrn
    root_bankid = "25"
    status_code = "00"
    remarks = acknowledgement_no
    root_effective_balance = str(decrypted_obj.get("NetBalance", ""))
    root_ifsc_code = decrypted_obj.get("IFSCCode", "")

    # ATM
    if "ATM CSW" in txn_desc:
        # Parse ATM fields
        # Example: ATM CSW/0120068848/SIVANANATHA COLON/COIMBAT
        txn_split = txn.get('TransactionDescription').split('/')
        atm_id = txn_split[1]
        place_of_atm = txn_split[2]
        atm_of_bank = ""
        i4c_payload = {
            "acknowledgement_no": acknowledgement_no,
            "Job_id": job_id,
            "transactions": [
                {
                    "txn_type": "Withdrawal through ATM",
                    "txn_type_id": "5",
                    "amount": str(txn_amount),
                    "disputed_amount": str(disputed_amt),
                    "transaction_datetime": transaction_datetime,
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
        txn_split = txn.get('TransactionDescription').split('/')
        mid = txn_split[2]
        tid = txn_split[2]
        approval_code = txn_split[2]
        merchant_name = txn_split[3]
        pos_transaction_id = txn.get("ChequeNumber", "")
        i4c_payload = {
            "acknowledgement_no": acknowledgement_no,
            "Job_id": job_id,
            "transactions": [
                {
                    "txn_type": "Withdrawal through POS",
                    "txn_type_id": "11",
                    "amount": str(txn_amount),
                    "disputed_amount": str(disputed_amt),
                    "transaction_datetime": transaction_datetime,
                    "phone_number": phone_number,
                    "email": email,
                    "pan_number": pan_number,
                    "mid": mid,
                    "tid": tid,
                    "approval_code": approval_code,
                    "merchant_name": merchant_name,
                    "pos_transaction_id": pos_transaction_id,
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
        branch_code = txn.get("BranchCode", "")
        location = txn.get("BranchName", "")

        # 🔹 fetch from DB
        branch_manager = get_branch_manager(db, branch_code)

        if branch_manager:
            managername = branch_manager.emp_name
            managernumber = branch_manager.mobile
        else:
            managername = ""
            managernumber = ""

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
                    "withdrawal_date": transaction_datetime,
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

    return call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'], log_file_name)

