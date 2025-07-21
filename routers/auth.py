from fastapi import APIRouter, Depends
from pydantic import BaseModel
import logging
from utils.custom_class import APIRouteWrapper
import os
from dotenv import load_dotenv
from utils.aes_encryption_decryption import AESUtil
from utils.external_api import APIRequester
from router_helper.login_helper import (
    lms_login,
    fetch_user_details,
    user_not_found_response,
)

from fastapi.security import OAuth2PasswordRequestForm
import orjson
from fastapi.responses import JSONResponse, ORJSONResponse
import json

router = APIRouter(route_class=APIRouteWrapper)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

aes = AESUtil()
requester = APIRequester()
AES_SECRET_KEY = os.getenv("AES_SECRET_KEY")


class EncryptedPayload(BaseModel):
    encrypted_payload: str


@router.post("/api/login", tags=["Auth"])
def user_login_encrypt(payload: EncryptedPayload):
    """
    Authenticate the user using the mobile number.
    If successful, create a JWT token and return it.
    """
    plaintext = aes.decrypt_password_payload(payload.encrypted_payload)
    print("plaintext", plaintext)
    plaintext.pop("origin", "").upper()

    user_details, _ = fetch_user_details(plaintext)
    if not user_details:
        return user_not_found_response(plaintext)
    # if not verify_password(plaintext.get("password"), user_details[0].get("user_password")):
    #     return password_incorrect_response()
    return lms_login(user_details[0].get("emp_code"))


@router.post("/token", tags=["Auth"])
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    """
    Obtain an access token using username and password.
    """
    raw_payload = json.dumps(
        {
            "emp_code": form_data.username,
            "password": form_data.password,
            "origin": "web",
            "device_id": None,
        }
    )
    encrypt_payload: EncryptedPayload = {
        "encrypted_payload": aes.encrypt_password_payload(raw_payload)
    }
    # Call the user_login_encrypt function and process the response
    login_response_obj = user_login_encrypt(EncryptedPayload(**encrypt_payload))

    # Check if the response is of ORJSONResponse type
    if isinstance(login_response_obj, ORJSONResponse):
        login_response = orjson.loads(login_response_obj.body)
    else:
        raise TypeError("Expected ORJSONResponse")

    print("login_response.get('data')", login_response.get("data"))
    # Extract the token from the response (ensure your response includes the token)
    token = login_response.get("data").get("access_token")
    if not token:
        return JSONResponse(
            content={"detail": "Invalid login response"}, status_code=401
        )

    # Return the response in a format Swagger expects
    return {"access_token": token, "token_type": "bearer"}
