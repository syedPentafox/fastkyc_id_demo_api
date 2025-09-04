import os
import logging
from .background_jobs_file_logger import add_background_jobs_file_handler
import json
from datetime import datetime
from utils.aes_encryption_decryption import AESUtil
import requests

def call_hold_funds_api(kvb_endpoint, hold_fund_path, disputed_amount, data, userid, kvb_key, src_channel, username, password, log_file_name):
    # hold_fund_path = os.getenv("HOLD_FUND_PATH", "/ESB/ForceHoldMaintenance")
    logger = logging.getLogger(log_file_name)
    logger.info(f"======= [HOLD_FUNDS_START] =======")
    hold_fund_url = kvb_endpoint.rstrip("/") + "/" + hold_fund_path.lstrip("/")
    # Capture timestamp to return to caller
    hold_timestamp = datetime.now()
    today_str = hold_timestamp.strftime("%Y%m%d")
    payload_data = data.get("request", {})
    instrument_data = payload_data.get("instrument", {})
    acknowledgement_no = str(payload_data.get("acknowledgement_no", ""))
    payer_account_number = str(instrument_data.get("payer_account_number", ""))
    transaction_branch = payer_account_number[:4] if len(payer_account_number) >= 4 else ""
    cbs_user_id = str(userid)
    hold_amount = "{:.2f}".format(disputed_amount)
    hold_fund_dict = {
        "CBSUserID": cbs_user_id,
        "TransactionBranch": transaction_branch,
        "AccountNumber": payer_account_number,
        "HoldAmount": hold_amount,
        "EarMarkType": "32",
        "Reason": "7",
        "Narration": f"CC {acknowledgement_no}",
        "ExpiryDate": "20991231",
        "TransactionType": "A",
        "HoldNumber": "",
        "TransactionDate": today_str
    }
    encrypted_hold = AESUtil().aes_encrypt(kvb_key, json.dumps(hold_fund_dict))
    curl_data = json.dumps({
        "in_msg": {
            "Src_Channel": src_channel,
            "UserName": username,
            "Password": password,
            "encryptReq": encrypted_hold
        }
    })
    hold_post_payload = {
        "in_msg": {
            "Src_Channel": src_channel,
            "UserName": username,
            "Password": password,
            # "UserId": userid,
            "encryptReq": encrypted_hold
        }
    }
    is_success = False
    logger.info(f"[HOLD_FUNDS_CURL] curl -X POST '{hold_fund_url}' -H 'Content-Type: application/json' -d '{curl_data}'")
    try:
        logger.info(f"[KVB_HOLD_API_ENDPOINT] {hold_fund_url}")
        logger.info(f"[KVB_HOLD_API_REQUEST] {json.dumps(hold_post_payload, indent=4)}")
        hold_resp = requests.post(hold_fund_url, json=hold_post_payload, timeout=30)
        logger.info(f"[KVB_HOLD_API_RESPONSE] {hold_resp.status_code} {hold_resp.text}")
        hold_resp_json = hold_resp.json()
        hold_encrypt_res = hold_resp_json.get("out_msg", {}).get("encryptRes")
        if hold_encrypt_res:
            decrypted_hold = AESUtil().aes_decrypt(kvb_key, hold_encrypt_res)
            logger.info(f"[KVB_HOLD_DECRYPTED_RESPONSE] {decrypted_hold}")
            try:
                decrypted_obj = json.loads(decrypted_hold)
                error_code = decrypted_obj.get("ErrorCode")
                error_message = decrypted_obj.get("ErrorMessage")
                if str(error_code) == "0" and str(error_message).lower() == "success":
                    is_success = True
                    logger.info(f"[KVB_HOLD_SUCCESS] {json.dumps(decrypted_obj, indent=4)}")
                else:
                    # FIXME: error in KVB_ENDPOINT
                    logger.error(f"[KVB_HOLD_ERROR] {json.dumps(decrypted_obj, indent=4)}")
            except Exception as dec_exc:
                # FIXME: error in KVB_ENDPOINT
                logger.error(f"[KVB_HOLD_DECODE_ERROR] {dec_exc}")
        logger.info(f"======= [HOLD_FUNDS_END] =======")
        return hold_timestamp, is_success
    except Exception as hold_api_exc:
        logger.error(f"[KVB_HOLD_API_ERROR] {hold_api_exc}")
        logger.info(f"======= [HOLD_FUNDS_END] =======")
        return hold_timestamp, is_success
