def import_table_metadata(table_metadata, tables):
  # Manually add i4c_request table metadata (Oracle filters out SYSTEM tablespace tables)
  if 'i4c_request' not in table_metadata:
    table_metadata['i4c_request'] = ['request', 'ack_no', 'job_id', 'status', 'msg_type', 'received_dt', 'created_date', 'modified_date', 'created_by', 'modified_by']
    tables.append('i4c_request')
    
  if 'upi_fraud_transactions' not in table_metadata:
    # table_metadata['upi_fraud_transactions'] = ['id', 'job_id', 'sub_category', 'requestor', 'payer_bank_code', 'mode_of_payment', 'payer_mobile_number', 'payer_account_number', 'state', 'district', 'received_dt', 'incident_response']
    table_metadata['upi_fraud_transactions'] = ['job_id', 'sub_category', 'requestor', 'payer_bank_code', 'mode_of_payment', 'payer_mobile_number', 'payer_account_number', 'state', 'district', 'received_dt', 'incident_response']
    tables.append('upi_fraud_transactions')
    
  if 'upi_fraud_incidents' not in table_metadata:
    table_metadata['upi_fraud_incidents'] = ['ack_no', 'job_id', 'amount', 'rrn', 'transaction_date', 'transaction_time', 'disputed_amount', 'layer']
    tables.append('upi_fraud_incidents')