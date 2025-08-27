from background_jobs.payment_status_inquiry_api import payment_status_inquiry_api
from background_jobs.i4c_response_api import call_i4c_response_api
import os
import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
from background_jobs.upi_payment_status_inquiry_api import upi_payment_status_inquiry_api

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
add_background_jobs_file_handler(logger)

def money_transfer_to_non_upi(decrypted_obj, data, transaction_type, response_table, rrn, transaction_datetime, amount, root_account_number):
  kvb_endpoint = os.getenv("KVB_ENDPOINT", "")
  payment_status_path = os.getenv("PAYMENT_STATUS_INQUIRY_PATH", "/ESB/PaymentStatusInquiry")
  kvb_key = os.getenv("KVB_KEY_VALUE")
  src_channel = os.getenv("KVB_SRC_CHANNEL")
  username = os.getenv("KVB_USERNAME")
  password = os.getenv("KVB_PASSWORD")
  
  # Prepare payment inquiry payload
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
      password
  )
  logger.info(f"[PAYMENT_STATUS_INQUIRY_DEBIT] Response: {payment_status_response}")
  payee_account_number = ""
  if payment_status_response and isinstance(payment_status_response, dict):
      payee_account_number = payment_status_response.get("Beneficiary_Account_No", "") if payment_status_response else ""
  
  i4c_payload = {
      "acknowledgement_no": data.get("request", {}).get("acknowledgement_no", ""),
      "job_id": data.get("job_id", ""),
      "transactions": [
          {
              "txn_type": "Money Transfer To",
              "txn_type_id": "3",
              "amount": amount,
              "disputed_amount": amount,
              "transaction_datetime": transaction_datetime,
              "phone_number": "1234567890",
              "email": "testing@gmail.com",
              "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
              "ifsc_code": decrypted_obj.get("IFSCCode", ""),
              "root_account_number": root_account_number,
              "root_rrn_transaction_id": rrn,
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

  return call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'])

def money_transfer_to_upi(decrypted_obj, data, rrn, txn_date_formatted, amount, transaction_datetime, payer_account_number, response_table):
  kvb_endpoint = os.getenv("KVB_ENDPOINT", "")
  upi_payment_status_path = os.getenv("UPI_PAYMENT_STATUS_INQUIRY_PATH", "/ESB/UPITransactionEnquiry")
  upi_payment_status_url = kvb_endpoint.rstrip("/") + "/" + upi_payment_status_path.lstrip("/")
  kvb_key = os.getenv("KVB_KEY_VALUE")
  src_channel = os.getenv("KVB_SRC_CHANNEL")
  username = os.getenv("KVB_USERNAME")
  password = os.getenv("KVB_PASSWORD")

  # reference_id = instrument.get("reference_id", "")
  # txn_date_str = instrument.get("transaction_date", "")
  # txn_date_formatted = ""
  # try:
  #     date_part = txn_date_str.split()[0] if txn_date_str else ""
  #     if date_part:
  #         day, month, year = date_part.split('-')
  #         import calendar
  #         month_name = calendar.month_abbr[int(month)]
  #         txn_date_formatted = f"{int(day)}-{month_name}-{year}"
  # except Exception as date_exc:
  #     logger.warning(f"[UPI_TXN_DATE_FORMAT] Could not format txn date: {txn_date_str}, error: {date_exc}")
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
      password
  )
  logger.info(f"[UPI_PAYMENT_STATUS_INQUIRY_DEBIT] Response: {upi_response}")
  payee_account_number = ""
  if upi_response and isinstance(upi_response, dict):
      payee_account_number = upi_response.get("PayeeAccountNumber", "") if upi_response else ""
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
              "amount": amount,
              "disputed_amount": amount,
              "transaction_datetime": transaction_datetime,
              "phone_number": "1234567890",
              "email": "testing@gmail.com",
              "pan_number": decrypted_obj.get("PAN", "") or "FORM60",
              # "disputed_amount": amount,
              "ifsc_code": decrypted_obj.get("IFSCCode", ""),
              "root_account_number": payer_account_number,
              "root_rrn_transaction_id": rrn,
              "root_bankid": "25",
              "status_code": "00",
              "remarks": data.get("request", {}).get("acknowledgement_no", ""),
              "root_effective_balance": str(decrypted_obj.get("NetBalance", "")),
              "root_ifsc_code": decrypted_obj.get("IFSCCode", "")
          }
      ]
  }
  is_success = call_i4c_response_api(i4c_payload, kvb_key, kvb_endpoint, response_table, data['received_dt'])
