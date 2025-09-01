from fastapi.responses import JSONResponse
from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute
from fastapi.encoders import jsonable_encoder
from utils.authentication import get_user_id_from_token
import traceback
from orm_model.core_models import CollectionField

from datetime import date, datetime
from pydantic import BaseModel, create_model
from typing import List, Dict, Any, Type, Optional, Callable

import json
from enum import Enum
import logging
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, DataError
from orm_model.core_models import ResourcePermissionsValidation
from utils.db_connection import db


logging.basicConfig()


def create_enum(name: str, values: List[str]) -> Type[Enum]:
    """Dynamically create an Enum with the given name and values."""
    return Enum(name, {value: value for value in values})


def get_field_type(
    collection: str, filed_name: str, interface: str, data_type: str, options: str
) -> Any:
    if interface == "DROPDOWN":
        if options:
            enum_values = json.loads(options)
            print("enumvalues", enum_values)
            enum_name = f"{collection}_{filed_name}_Enum"
            return Enum(
                enum_name, {value.replace(" ", "_"): value for value in enum_values}
            )
        return str
    elif interface == "CHECKBOX":
        return bool
    elif interface == "DATE":
        return date
    elif interface == "NUMERIC":
        return int
    elif interface == "FORM_SEARCH":
        return str if data_type == "STRING" else int
    elif interface == "STRING":
        return dict if data_type == "JSON" else str
    elif interface == "DATETIME":
        return datetime
    elif interface == "TEXT":
        return dict if data_type == "JSON" else str
    else:
        return Any


def create_dynamic_model(
    data: List[Dict[str, Any]], required_fields
) -> Type[BaseModel]:
    fields = {}
    for item in data:
        field_name = item["field"]
        field_type = get_field_type(
            item["collection"],
            item["field"],
            item["interface"],
            item["data_type"],
            item["options"],
        )
        if int(item["id"]) in required_fields:
            fields[field_name] = field_type, ...
        else:
            fields[field_name] = (Optional[field_type], None)

    dynamic_model = create_model("DynamicModel", **fields)
    return dynamic_model


models = {}


# Dependency to get the dynamic model based on the path and user ID
async def get_dynamic_model(request: Request) -> Type[BaseModel]:
    user_id = await get_user_id_from_token(request)
    path = request.url.path
    # Assuming the model is stored with a key combining user_id and path
    model_key = f"{user_id}{path}"
    dynamic_model = models.get(model_key)
    if not dynamic_model:
        raise HTTPException(
            status_code=404, detail="Model not found for the specified path"
        )
    return dynamic_model


def get_allowed_columns(filters={"role": 1}):
    permissions = db.query(ResourcePermissionsValidation).filter_by(**filters).all()
    if not permissions:
        return []
    for permission in permissions:
        resource = permission.__dict__.get("api")
        role = str(permission.__dict__.get("role"))
        method = str(permission.__dict__.get("method"))
        key = role + "#" + method + "#" + resource
        if method == "GET":
            allowed_column_ids = permission.__dict__.get("fields", [])
            required_fields = []
        else:
            optional_fields = permission.__dict__.get("optional_fields", [])
            required_fields = permission.__dict__.get("required_fields", [])
            allowed_column_ids = required_fields + optional_fields
        if allowed_column_ids:
            allowed_columns = (
                db.query(CollectionField)
                .filter(CollectionField.id.in_(allowed_column_ids))
                .order_by(CollectionField.sort.asc())
                .all()
            )
            columns = [column.__dict__ for column in allowed_columns]
            pydantic_model = create_dynamic_model(columns, required_fields)
            models.update({key: pydantic_model})
            print("KKKKKKKKKK", models)


async def default_exception_handler(request, err, custom_message=None):
    """
    Handles the exception and notifies the user via a chat app
    :param request: HTTP request made by the client
    :param request_json: HTTP request json made by the client
    :param err: exception
    :param custom_message: If user needs to give custom message
    :return: JSON response delineating the request and exception
    In case of RequestValidationError, the inbuilt error handling mechanism have a default format of JSON response.
    It is now made custom in a more user friendly format.
    Formatting plus sending the incoming request in the response for easy reconciliation.

    Example of default format:
    {"detail":[{"loc":["body","first_name"],"msg":"ensure this value has at least 2 characters","type":
    "value_error.any_str.min_length","ctx":{"limit_value":2}}]}

    Example of custom format:
    {"RequestValidationError":{"first_name":"ensure this value has at least 2 characters"},"Request":{"first_name":"r",
    "last_name":"","mobile":9000000003,"email":"raj.india18@gmail.com","password":"Digi@ops22",
    "group_id":1,"status":1,"designation":"Manager"}}
    """
    if err.__class__.__name__ == "RequestValidationError":
        error_list = err.errors()
        consolidated_validation_msg = {}
        for error in error_list:
            consolidated_validation_msg.update({error.get("loc")[-1]: error.get("msg")})
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder(
                {
                    "RequestValidationError": consolidated_validation_msg,
                    "Request": err.body,
                }
            ),
        )
    """By default for all exceptions except RequestValidationError the following custom_message is provided"""
    if not custom_message:
        custom_message = (
            "Couldn't {0}, contact support at (+91)7867913618.".format(request.method)
            .replace("GET", "fetch record")
            .replace("POST", "add or edit record")
            .replace("PUT", "add or edit record")
            .replace("DELETE", "remove record")
        )
    traceback_message = "".join(
        traceback.format_exception(None, err, err.__traceback__)
    )
    print("traceback_message>>>>>>", traceback_message)
    return JSONResponse(content=dict(status="error", message=custom_message))


def http_exception_handler(request, exc: Exception):
    """
    Handles the HTTPException and sends a custom message instead of a default message
    :param request: the request object
    :param exc: the exception object
    :return: A json
    """
    traceback_message = "".join(
        traceback.format_exception(None, exc, exc.__traceback__)
    )
    print("traceback_message>>>>>>", traceback_message)
    return JSONResponse(
        status_code=exc.status_code,
        content={"data": {}, "status": "error", "message": str(exc.detail)},
    )


def handle_sqlalchemy_error(e: SQLAlchemyError):
    traceback_message = "".join(traceback.format_exception(None, e, e.__traceback__))
    logging.info(f"Database error: {traceback_message} \n {str(e)}")
    if isinstance(e, IntegrityError):
        if "duplicate key value violates unique constraint" in str(e):
            conflicting_values = str(e).split("=")[-1].split("(")[1].split(")")[0]
            custom_message = f"Duplicate entry for values: {conflicting_values}."
        elif "foreign key constraint" in str(e):
            column_name = str(e).split("Key (")[1].split(")")[0]
            table_name = str(e).split('"')[-2]
            custom_message = f"""Foreign key constraint error: The value for column '{column_name}'
            does not exist in the '{table_name}' table."""
        else:
            custom_message = "A data error occurred. Please check that your file data is entered correctly"
    elif isinstance(e, DataError):
        custom_message = "A data error occurred. Please check that your file data is entered correctly"
    else:
        custom_message = "Database error occurred."
    print("traceback_message>>>>>>", traceback_message)
    return JSONResponse(content=dict(status="error", message=custom_message))


class CustomRequest(Request):
    """
    Request object is inherited to add a new attribute "logged_in_user_id" within the Request object.
    This attribute will be used within the api route functions.
    """

    def __init__(self):
        self.logged_in_user_id: Optional[int] = None
        self.validated_payload: Dict[str, Any] = {}
        self.path: Dict[str, Any] = {}


class APIRouteWrapper(APIRoute):
    def get_route_handler(self) -> Callable:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: CustomRequest) -> Response:
            """
            Centralized request handling for all routes.
            Handles user authorization (via JWT or custom headers) and provides custom exception handling.

            - Excluded paths bypass authorization.
            - Logs request attributes for debugging.
            - Routes errors through custom handlers.

            :param request: The incoming HTTP request
            :return: The response generated by the route
            """
            # Debugging request attributes
            print("Request Attributes:")
            print(f"Method: {request.method}")
            print(f"URL: {request.url}")
            print(f"Headers: {request.headers}")
            print(f"Query Params: {request.query_params}")
            print(f"Path Params: {request.path_params}")
            print(f"Cookies: {request.cookies}")
            print(f"Client: {request.client}")
            print(f"Route Path: {self.path}")

            # Paths that bypass authorization
            excluded_paths = [
                "/api/user/login",
                "/api/user-signup",
                "/api/login",
                "/api/verify-otp",
                "/api/refresh",
                "/admin/login",
                "/token",
                "/api/i4c_request",
                "/ncrp/api/login",
                "/api/collection/tables/{table_name}",
                "/api/items/{collection}"
            ]

            # Authorization logic for protected routes
            if self.path not in excluded_paths:
                try:
                    logged_in_user_id = await get_user_id_from_token(request)
                    request.logged_in_user_id = int(logged_in_user_id)
                    request.path = self.path
                except HTTPException as e:
                    print("Authorization failed:", e.detail)
                    raise e
                except Exception as auth_exc:
                    print("Unexpected authorization error:", auth_exc)
                    raise HTTPException(status_code=401, detail="Authorization failed")

            # Exception handling
            try:
                return await original_route_handler(request=request)
            except HTTPException as e:
                print("HTTPException occurred:", e.detail)
                return http_exception_handler(request=request, exc=e)
            except SQLAlchemyError as db_exc:
                print("SQLAlchemyError occurred:", str(db_exc))
                return handle_sqlalchemy_error(db_exc)
            except Exception as exc:
                print("Unhandled Exception:", str(exc))
                # Access request body for detailed error reporting
                try:
                    await request.body()
                except Exception as body_exc:
                    print("Failed to access request body:", str(body_exc))
                return await default_exception_handler(request=request, err=exc)

        return custom_route_handler
