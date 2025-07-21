from fastapi import (
    Query,
    APIRouter,
    Depends,
)

from utils.db_connection import db
import json


import logging
from utils.custom_class import APIRouteWrapper, CustomRequest


from sqlalchemy import Enum

from response_models.response_models import make_success_response, make_failure_response


from utils.authentication import verify_access_token

router = APIRouter(
    route_class=APIRouteWrapper, dependencies=[Depends(verify_access_token)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@router.get("/api/rbac/modules", tags=["RBAC"])
def get_modules(
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
):
    allowed_columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    collection = "modules"

    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return make_success_response(
            data=data, message="Modules fetched successfully", metadata=metadata
        )
    return make_success_response(data=[], message="No modules found", metadata=[])


@router.post("/api/rbac/modules", tags=["RBAC"])
def submit_modules(data: dict, request: CustomRequest = None):
    new_record = db.create_record("modules", data, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}],
        message="resources submitted successfully",
        metadata=[],
    )


@router.get("/api/rbac/resources", tags=["RBAC"])
def get_resources(
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
):
    allowed_columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    collection = "resources"

    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return make_success_response(
            data=data, message="resources fetched successfully", metadata=metadata
        )
    return make_success_response(data=[], message="No resources found", metadata=[])


@router.post("/api/rbac/resources", tags=["RBAC"])
def submit_resources(data: dict, request: CustomRequest = None):
    new_record = db.create_record("resources", data, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}],
        message="resources submitted successfully",
        metadata=[],
    )


@router.get("/api/rbac/collections", tags=["RBAC"])
def get_collections(
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
):
    allowed_columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    collection = "collections"

    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return make_success_response(
            data=data, message="collections fetched successfully", metadata=metadata
        )
    return make_success_response(data=[], message="No collections found", metadata=[])


@router.post("/api/rbac/collections", tags=["RBAC"])
def submit_collections(data: dict, request: CustomRequest = None):
    new_record = db.create_record("collections", data, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}],
        message="collections submitted successfully",
        metadata=[],
    )


@router.get("/api/rbac/permissions", tags=["RBAC"])
def get_permissions(
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
):
    allowed_columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    collection = "resource_permissions_validations"
    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return make_success_response(
            data=data, message="collections fetched successfully", metadata=metadata
        )
    return make_success_response(data=[], message="No collections found", metadata=[])


@router.get("/api/rbac/module_resource_map", tags=["RBAC"])
def get_module_resource_map(
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
):
    allowed_columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    allowed_columns = ["*.*"]
    collection = "module_resource_map"
    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return make_success_response(
            data=data, message="collections fetched successfully", metadata=metadata
        )
    return make_success_response(data=[], message="No collections found", metadata=[])


@router.get("/api/user/permissions", tags=["RBAC"])
def get_user_role_permissions(
    page: int = 1, per_page: int = Query(10, ge=1), request: CustomRequest = None
):
    allowed_columns = ["module.*", "resource.*"]
    collection = "resource_permissions_validations"

    result = db.get_record_by_id("users", request.logged_in_user_id, ["role"])

    filters_dict = {"role_eq": result[0].get("role")}
    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection, allowed_columns, filters_dict, page=page, per_page=per_page
        )
        return make_success_response(
            data=data, message="collections fetched successfully", metadata=metadata
        )
    return make_success_response(data=[], message="No collections found", metadata=[])


def check_duplicates(optional_fields, required_fields):
    duplicates = set(required_fields) & set(optional_fields)
    if duplicates:
        return (
            False,
            f"Duplicate fields found in required and optional fields: {duplicates}",
        )
    return True, ""


@router.post("/api/rbac/permissions", tags=["RBAC"])
def add_role_permission(data: dict, request: CustomRequest = None):
    valid, message = check_duplicates(
        data.get("optional_fields"), data.get("required_fields")
    )

    if not valid:
        return make_failure_response(message=message)

    new_record = db.upsert_record(
        "resource_permissions_validations",
        data,
        ["role", "resource"],
        request.logged_in_user_id,
    )
    return make_success_response(
        data=[{"id": new_record}],
        message="collections submitted successfully",
        metadata=[],
    )


@router.post("/api/rbac/revoke/permissions", tags=["RBAC"])
def delete_role_permission(data: dict, request: CustomRequest = None):
    for resource_id in data.get("resource_ids"):
        print("ids", resource_id)
        db.delete_record(
            "resource_permissions_validations",
            resource_id,
            user_id=request.logged_in_user_id,
        )
    return make_success_response(
        data=[], message="Permission removed successfully", metadata=[]
    )


@router.get("/api/rbac/{collection}/fields", tags=["RBAC"])
def get_collectionfields(
    collection: str,
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
):
    allowed_columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    filters_dict.update({"collection_eq": collection})
    collection = "collection_fields"
    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return make_success_response(
            data=data, message="collection fields fetched", metadata=metadata
        )
    return make_success_response(data=[], message="no collection fileds", metadata=[])


@router.post("/api/rbac/fields", tags=["RBAC"])
def create_collection_fields(data: dict, request: CustomRequest = None):
    new_record = db.create_record("collection_fields", data, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}], message="field created", metadata=[]
    )


@router.patch("/api/rbac/fields/{id}", tags=["RBAC"])
def collection_fields_update(id: int, data: dict, request: CustomRequest = None):
    db.update_record("collection_fields", id, data, request.logged_in_user_id)
    return make_success_response(data=[], message="updated", metadata=[])


def get_interface_datatype(column, foreign_keys):
    print("column.get('type') ", column["name"], type(column.get("type")))
    column_type = str(column.get("type"))

    if column["name"] in foreign_keys:
        data_type = "INT" if column_type == "INTEGER" else "STRING"
        return "FORM SEARCH", data_type
    elif isinstance(column.get("type"), Enum):
        return "DROPDOWN", "STRING"
    if column_type == "INTEGER":
        return "NUMERIC", "INT"
    if column_type == "NUMERIC":
        return "NUMERIC", "FLOAT"
    elif column_type == "BOOLEAN":
        return "CHECKBOX", "BOOL"
    elif column_type == "JSON":
        return "JSON", "JSON"
    elif column_type == "DATE":
        return "DATE", "DATE"
    elif column_type == "DATETIME":
        return "DATETIME", "TIMESTAMP"
    elif column_type == "VARCHAR":
        return "TEXT", "STRING"
    else:
        return "TEXT", "TEXT"


@router.get("/api/fields", tags=["RBAC"])
def genearate_fields(request: CustomRequest = None):
    collection = "customer_requests"
    columns = db.get_columns_by_table(collection)

    collection_fields = []
    foreign_keys = {
        fk["constrained_columns"][0]: fk
        for fk in db.get_foreign_keys_by_table(collection)
    }
    print("foreign_keys:", foreign_keys)
    for column in columns:
        interface, data_type = get_interface_datatype(column, foreign_keys.keys())
        field = {
            "collection": collection,
            "field": column["name"],
            "label": column["name"].replace(
                "_", " "
            ),  # Modify this as per your requirement
            "type": str(column["type"]),
            "interface": interface,
            "data_type": data_type,
            "options": [enum for enum in column.get("type").enums]
            if isinstance(column.get("type"), Enum)
            else [],
            "is_required": not column["nullable"],
            "is_primary_key": column.get("primary_key", False),
            "has_auto_increment": column.get("autoincrement", False),
            "max_length": column.get("length"),
            "numeric_precision": column.get("precision"),
            "numeric_scale": column.get("scale"),
            "foreign_key_column": foreign_keys[column["name"]]["referred_columns"][0]
            if column["name"] in foreign_keys
            else None,
            "foreign_key_table": foreign_keys[column["name"]]["referred_table"]
            if column["name"] in foreign_keys
            else None,
            "sort": len(collection_fields),
        }
        collection_fields.append(field)
    return make_success_response(
        data=collection_fields,
        message="collections submitted successfully",
        metadata=[],
    )
