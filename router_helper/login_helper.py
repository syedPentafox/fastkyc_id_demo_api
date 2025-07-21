from utils.aes_encryption_decryption import AESUtil
from utils.external_api import APIRequester
from response_models.response_models import make_success_response, make_failure_response
from routers.main import db
from datetime import datetime
import logging
from utils.authentication import create_access_token, create_refresh_token

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
aes = AESUtil()
requester = APIRequester()


def fetch_user_details(plaintext):
    return db.get_data_from_table(
        "users",
        ["id", "emp_code", "mobile", "is_active", "user_password"],
        {"emp_code_eq": plaintext.get("emp_code").strip().upper()},
    )


def user_not_found_response(plaintext):
    return make_failure_response(
        message=f"User with AD Code : {plaintext.get('emp_code')} does not exist"
    )


def user_inactive_response(plaintext):
    return make_failure_response(
        message=f"User with AD Code : {plaintext.get('emp_code')} in-active"
    )


def password_incorrect_response():
    return make_failure_response(message="Password is incorrect")


def upsert_user_session(user_id, token):
    data = {"user_id": user_id, "token": token, "created_at": datetime.now()}
    token_details, _ = db.get_data_from_table(
        "user_session_tokens", ["*.*"], {"user_id_eq": int(user_id)}
    )
    print("TOken", token_details)
    if token_details:
        db.update_record(
            "user_session_tokens", token_details[0].get("id"), data, user_id
        )
    else:
        db.create_record("user_session_tokens", data, user_id)


def lms_login(emp_code):
    user, _ = db.get_data_from_table("users", ["*.*"], {"emp_code_eq": emp_code})
    if not user:
        return make_failure_response(
            message=f"User with Employee code:{emp_code} does not exist"
        )
    if user[0].get("user_password"):
        user[0].pop("user_password")
    access_token = create_access_token(data={"user_id": user[0].get("id")})
    refresh_token = create_refresh_token(data={"user_id": user[0].get("id")})
    logger.info(" Generating response ")
    # upsert_user_session(user[0].get("id"),access_token)
    return make_success_response(
        data={
            **user[0],
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
        },
        message="login successful",
        metadata=[],
    )
