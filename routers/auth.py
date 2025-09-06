from fastapi import APIRouter
from pydantic import BaseModel
import logging
import os
from dotenv import load_dotenv
import json, requests
from response_models.response_models import make_failure_response, make_success_response
from utils.authentication import create_access_token_ncrp, create_refresh_token_ncrp
from utils.custom_class import APIRouteWrapper
from utils.aes_encryption_decryption import AESUtil
from utils.external_api import APIRequester

router = APIRouter(route_class=APIRouteWrapper)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

aes = AESUtil()
requester = APIRequester()
AES_SECRET_KEY = os.getenv("AES_SECRET_KEY")

class EncryptedPayload(BaseModel):
    encrypted_payload: str

def convert_to_dict(data):
    if isinstance(data, str):
        return json.loads(data)
    return data

@router.post("/ncrp/api/login")
def user_login(payload: EncryptedPayload):
    plaintext = aes.decrypt_password_payload(payload.encrypted_payload)
    username = plaintext.get("user_name")
    password = plaintext.get("password")
    if not username or not password:
        return make_failure_response(message="Username and password are required.")
    ad_plain = {"Usr_Name": username, "Usr_Psw": password, "Source": "AD"}
    encrypted_req = aes.encrypt_ad_password_payload(json.dumps(ad_plain))
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
    if not resp.ok:
        return make_failure_response(message="Couldn't reach AD server")

    resp_json = resp.json()
    decrypted = {}

    out_msg = resp_json.get("out_msg")
    if isinstance(out_msg, str):
        out_msg = json.loads(out_msg)

    if out_msg and out_msg.get("encryptRes"):
        decrypted = aes.decrypt_ad_password_payload(out_msg["encryptRes"])
        if not decrypted:
            return make_failure_response(message="User credentials invalid.")

    if decrypted.get("ErrorMessage") == "Success":
        # if decrypted.get("Department") not in ["ITD", "OD", "1260"]:
        #     return make_failure_response(message="Unauthorized Department")
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
        return make_success_response(data=final_payload)

    return make_failure_response(message=decrypted.get("ErrorMessage"))
