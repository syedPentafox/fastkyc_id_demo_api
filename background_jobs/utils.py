fraud_type_table_prefix = {
  'UPI Related Frauds': 'upi_fraud',

  'Internet Banking Related Fraud': 'internet_banking_fraud',

  'Fraud Call/Vishing': 'vishing_fraud',

  'Demat/Depository Fraud': 'demat_fraud',

  'Debit/Credit Card Fraud/Sim Swap Fraud': 'credit_card_fraud',
  'Debit/Credit Card Fraud': 'credit_card_fraud',
}

def is_response_success(decrypted_obj):
  error_code = decrypted_obj.get("ErrorCode")
  error_message = decrypted_obj.get("ErrorMessage")
  return str(error_code) == "0" and str(error_message).lower() == "success"