curl -X 'POST' \
  'http://localhost:8001/api/i4c-request' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "payload": {
  "acknowledgement_no": "32406250019920",
  "sub_category": "UPI Related Frauds",
  "instrument": {
    "requestor": "I4C-MHA",
    "payer_bank": "Karur Vysya Bank",
    "mode_of_payment": "CREDIT",
    "payer_bank_code": 25,
    "payer_account_number": "1219172000009820",
    "payer_mobile_number": "9777197252",
    "state": "ODISHA",
    "district": "NABARANGPUR",
    "transaction_type": "",
    "incidents": [
      {
        "rrn": "517038626495",
        "amount": 11600.0,
        "transaction_date": "2025-06-19",
        "transaction_time": "16:27:00",
        "disputed_amount": 3146.6,
        "layer": 5
      }
    ]
  }
},
  "ack_no": "32406250019920",
  "job_id": "KVB-dac1fd74-3f0b-496d-bbca-766c66ebcd21",
  "status": "N",
  "msg_type": "REQ",
  "received_dt": "14-07-25 1:15:47.000000000 PM"
}'