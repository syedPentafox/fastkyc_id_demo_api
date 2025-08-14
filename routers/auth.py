from fastapi import APIRouter, Depends, requests
from pydantic import BaseModel
import logging
from response_models.response_models import make_failure_response, make_success_response
from utils.authentication import create_access_token_ncrp, create_refresh_token_ncrp
from utils.custom_class import APIRouteWrapper, CustomRequest
import os
from dotenv import load_dotenv
from utils.aes_encryption_decryption import AESUtil
from utils.external_api import APIRequester
import json,requests

router = APIRouter(route_class=APIRouteWrapper)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

aes = AESUtil()
requester = APIRequester()
AES_SECRET_KEY = os.getenv("AES_SECRET_KEY")


class EncryptedPayload(BaseModel):
    encrypted_payload: str


@router.post("/api/login")
def user_login(payload: EncryptedPayload):
    logger.info(f"Encrypted payload from frontend: {payload.encrypted_payload}")
    plaintext = aes.decrypt_password_payload(payload.encrypted_payload)
    logger.info(f"Decrypted frontend payload: {plaintext}")
    print(f"Decrypted frontend payload: {plaintext}")
    username = plaintext.get("user_name")
    password = plaintext.get("password")
    if not username or not password:
        return make_failure_response(message="Username and password are required.")
    ad_plain = {"Usr_Name": username, "Usr_Psw": password, "Source": "AD"}
    encrypted_req = aes.encrypt_ad_password_payload(json.dumps(ad_plain))
    logger.info(f"Encrypted AD request: {encrypted_req}")
    print(f"Encrypted AD request: {encrypted_req}")
    kvb_payload = {
        "inputVariables": {
            "in_msg": {
                "Src_Channel": "APII4C",
                "UserName": os.getenv("KVB_USERNAME"),
                "Password": os.getenv("KVB_PASSWORD"),
                "encryptReq": encrypted_req
            }
        }
    }
    headers = {"Content-Type": "application/json"}
    resp = requests.post(os.getenv("AD_LOGIN"), json=kvb_payload, headers=headers, verify=False)
    logger.info(f"Raw AD API response: {resp.text}")
    print(f"Raw AD API response: {resp.text}")
    if not resp.ok:
        return make_failure_response(message="Couldn't reach AD server")
    resp_json = resp.json()
    out_msg = resp_json.get("out_msg")
    if isinstance(out_msg, str):
        try:
            out_msg = json.loads(out_msg)
        except json.JSONDecodeError:
            out_msg = {}
    decrypted = {}
    if isinstance(out_msg, dict) and "encryptRes" in out_msg:
        encrypt_res = out_msg["encryptRes"].strip()
        logger.info(f"Encrypted AD response: {encrypt_res}")
        print(f"Encrypted AD response: {encrypt_res}")
        try:
            decrypted = aes.decrypt_ad_password_payload(encrypt_res)
            logger.info(f"Decrypted AD response: {decrypted}")
            print(f"Decrypted AD response: {decrypted}")
        except Exception as e:
            return make_failure_response(message=f"Failed to decrypt AD response: {str(e)}")
    elif isinstance(out_msg, dict):
        decrypted = out_msg
        logger.info(f"Plain AD response: {decrypted}")
        print(f"Plain AD response: {decrypted}")
    else:
        return make_failure_response(message="Invalid out_msg format from AD")
    if decrypted.get("ErrorMessage") == "Success":
        if decrypted.get("Department") not in ["ITD", "OD", "1260"]:
            return make_failure_response(message="Unauthorized Department")
        user_id = decrypted.get("EmployeeCode")
        access_token = create_access_token_ncrp({"user_id": user_id})
        refresh_token = create_refresh_token_ncrp({"user_id": user_id})
        final_payload = {
            "user": decrypted,
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }
        encrypted_response = aes.encrypt_password_payload(json.dumps(final_payload))
        logger.info(f"Encrypted final response to frontend: {encrypted_response}")
        print(f"Encrypted final response to frontend: {encrypted_response}")
        return {"encrypted_payload": encrypted_response}
    else:
        return make_failure_response(message=decrypted.get("ErrorMessage"))