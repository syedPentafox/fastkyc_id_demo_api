curl -X 'POST' \
  'http://localhost:8001/api/i4c-request' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "payload": {
  "acknowledgement_no": "22406250007694",
  "sub_category": "UPI Related Frauds",
  "instrument": {
    "requestor": "I4C-MHA",
    "payer_bank": "Karur Vysya Bank",
    "mode_of_payment": "CREDIT",
    "payer_bank_code": 25,
    "payer_account_number": "1432155000158847",
    "payer_mobile_number": "9437121669",
    "state": "ODISHA",
    "district": "SAMBALPUR",
    "transaction_type": "",
    "incidents": [
      {
        "rrn": "517017083216",
        "amount": 7000.0,
        "transaction_date": "2025-06-19",
        "transaction_time": "17:44:28",
        "disputed_amount": 6996.14,
        "layer": 2
      }
    ]
  }
},
  "ack_no": "22406250007694",
  "job_id": "KVB-2792e1b9-caf6-4770-bf14-6bb8d0d0679e",
  "status": "N",
  "msg_type": "REQ",
  "received_dt": "14-07-25 12:57:14.000000000 PM"
}'