from fastapi import APIRouter, Depends


import logging
from utils.custom_class import APIRouteWrapper, CustomRequest
from utils.authentication import (
    create_access_token,
    get_user_id_from_refresh_token,
    get_password_hash,
)
from routers.main import db

from dotenv import load_dotenv

from response_models.response_models import make_success_response, make_failure_response
from router_helper.login_helper import (
    upsert_user_session,
    fetch_user_details,
)
from utils.authentication import verify_access_token

router = APIRouter(
    route_class=APIRouteWrapper, dependencies=[Depends(verify_access_token)]
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()


@router.post("/api/refresh", tags=["User Management"])
async def refresh_token(refresh_token: str):
    """
    Refreshes the user's access token using a valid refresh token. The provided refresh
    token is used to retrieve the associated user ID, and a new access token is generated and
    returned along with the token type.
    """
    user_id = await get_user_id_from_refresh_token(refresh_token)
    access_token = create_access_token(data={"user_id": user_id})
    upsert_user_session(user_id, access_token)
    return make_success_response(
        data={"access_token": access_token, "token_type": "bearer"},
        message="access token generated succesfully",
    )


@router.get("/api/user/login-history", tags=["User Management"])
def get_login_history(request: CustomRequest = None):
    """
    Retrieves the login history for the specified user. Optionally, the request can include
    a custom request object to filter or paginate the results.
    """
    user_history_details, metadata = db.get_data_from_table(
        "user_login_history",
        ["*.*"],
        {"user_id_eq": request.logged_in_user_id},
        request=request,
    )
    if user_history_details:
        return make_success_response(
            data=user_history_details,
            message="user login history retrieved successfully.",
            metadata=metadata,
        )
    return make_failure_response(message="No user login history found.")


@router.post("/api/create-user", tags=["User Management"])
def user_login(item: dict, request: CustomRequest = None):
    """
    When the user logs in using the mobile number, this API authenticates the user.
    If the authentication is successful, it creates a JWT token and sends it as a response.
    """
    item.update({"emp_code": item.get("emp_code", "").upper()})
    user_details, _ = fetch_user_details(item)
    if user_details:
        return make_failure_response(
            message=f"User with Code : {item.get('emp_code')} already exists"
        )
    item.update(
        {
            "user_password": get_password_hash(
                item.get("user_password", "Fly91_newuser")
            ),
            "plain_password": item.get("user_password"),
        }
    )
    new_record = db.create_record("users", item, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}], message="user created", metadata=[]
    )


@router.patch("/api/user/{user_id}/change-password", tags=["User Mangement"])
def change_user_password(user_id: int, item: dict, request: CustomRequest = None):
    """
    Used to reset the password and update the new password
    """
    hashed_password = {
        "user_password": get_password_hash(item.get("user_password")),
        "plain_password": item.get("user_password"),
    }
    db.update_record("users", user_id, hashed_password, request.logged_in_user_id)
    return make_success_response(
        data=[], message="Password reset successfull", metadata=[]
    )
