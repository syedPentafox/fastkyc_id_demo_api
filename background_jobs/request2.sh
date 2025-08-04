curl -X 'POST' \
  'http://localhost:8001/api/i4c-request' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "payload": {
      "acknowledgement_no": "33301250000003",
      "sub_category": "UPI Related Frauds",
      "instrument": {
        "requestor": "I4C-MHA",
        "payer_bank": "Karur Vysya Bank",
        "mode_of_payment": "CREDIT",
        "payer_bank_code": 25,
        "payer_account_number": "1128155000234891",
        "payer_mobile_number": "7358880034",
        "state": "Tamil Nadu",
        "district": "DINDIGUL",
        "transaction_type": "UPI",
        "incidents": [
          {
            "rrn": "435501551396",
            "amount": 54000.0,
            "transaction_date": "2024-12-20",
            "transaction_time": "22:46:43",
            "disputed_amount": 5000.0,
            "layer": 6
          }
        ]
      }
    },
    "ack_no": "33301250000003",
    "job_id": "KVB-dac1fd74-3f0b-496d-bbca-766c66ebcd21",
    "status": "N",
    "msg_type": "REQ",
    "received_dt": "14-07-25 1:15:47.000000000 PM"
  }'