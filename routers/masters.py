from fastapi import (
    Query,
    APIRouter,
    Depends,
)


from utils.db_connection import db
import json


import logging
from utils.custom_class import APIRouteWrapper, CustomRequest


from response_models.response_models import make_success_response
from utils.authentication import verify_access_token

router = APIRouter(
    route_class=APIRouteWrapper, dependencies=[Depends(verify_access_token)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


created_message = "data submitted successfully"
updated_message = "data updated successfully"
read_message = "data fetched successfully"


@router.get("/api/master/users", tags=["Masters"])
@router.get("/api/master/roles", tags=["Masters"])
@router.get("/api/master/states", tags=["Masters"])
@router.get("/api/master/branches", tags=["Masters"])
def get_master(
    page: int = 1,
    per_page: int = Query(10, ge=1),
    fields: str = "*.*",
    filters: str = Query(None),
    search: str = None,
    sort_by: str = None,
    group_by: str = None,
    aggregate: str = None,
    request: CustomRequest = None,
    download_file_type: str = None,
):
    """
    Retrieve user master data with filtering, sorting, and pagination options.
    """
    columns = fields.split(",") if fields else []
    sort_by = sort_by.split(",") if sort_by else []
    aggregate = json.loads(aggregate) if aggregate else {}
    group_by = json.loads(group_by) if group_by else {}
    filters_dict = json.loads(filters) if filters else {}

    collection = request.path.split("/")[-1]
    if download_file_type:
        data, _ = db.get_data_from_table(
            collection,
            ["*.*"],
            filters_dict,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
            request=request,
        )
        return db.export_as_file(
            data=data, file_type=download_file_type, file_name=collection
        )

    data, metadata = db.get_data_from_table(
        collection,
        columns,
        filters_dict,
        search,
        sort_by,
        page,
        per_page,
        aggregate,
        group_by,
        request=request,
    )
    return make_success_response(data=data, message=read_message, metadata=metadata)


@router.post("/api/master/users", tags=["Masters"])
@router.post("/api/master/roles", tags=["Masters"])
@router.post("/api/master/states", tags=["Masters"])
@router.post("/api/master/branches", tags=["Masters"])
def create_user(data: dict, request: CustomRequest = None):
    """
    Create a new user record.
    """
    collection = request.path.split("/")[-1]
    if collection == "users":
        data.update({"emp_code": data.get("emp_code").lower()})
    new_record = db.create_record(collection, data, request.logged_in_user_id)
    return make_success_response(
        data=[{"id": new_record}], message=created_message, metadata=[]
    )


@router.post("/api/master/users/{id}", tags=["Masters"])
@router.post("/api/master/roles/{id}", tags=["Masters"])
@router.post("/api/master/states/{id}", tags=["Masters"])
@router.post("/api/master/branches/{id}", tags=["Masters"])
def user_update(id: int, data: dict, request: CustomRequest = None):
    """
    Update an existing user record.
    """
    collection = request.path.split("/")[-2]
    db.update_record(collection, id, data, request.logged_in_user_id)
    return make_success_response(data=[], message=updated_message, metadata=[])
