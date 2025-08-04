curl -X 'POST' \
  'http://localhost:8001/api/i4c-request' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "payload": {
      "acknowledgement_no": "33701250000326",
      "sub_category": "UPI Related Frauds",
      "instrument": {
        "requestor": "I4C-MHA",
        "payer_bank": "Karur Vysya Bank",
        "mode_of_payment": "CREDIT",
        "payer_bank_code": 25,
        "payer_account_number": "1720155000076189",
        "payer_mobile_number": "6385171337",
        "state": "Tamil Nadu",
        "district": "CHENNAI",
        "transaction_type": "IMPS",
        "incidents": [
          {
            "rrn": "433722155603",
            "amount": 1200.0,
            "transaction_date": "2024-12-02",
            "transaction_time": "22:55:08",
            "disputed_amount": 100.0,
            "layer": 8
          }
        ]
      }
    },
    "ack_no": "33701250000326",
    "job_id": "KVB-dac1fd74-3f0b-496d-bbca-766c66ebcd21",
    "status": "N",
    "msg_type": "REQ",
    "received_dt": "14-07-25 1:15:47.000000000 PM"
  }'