from fastapi import Query, APIRouter, Depends

import json

import logging
from utils.custom_class import APIRouteWrapper, CustomRequest
from routers.main import db

from response_models.response_models import make_success_response

from utils.authentication import verify_access_token

router = APIRouter(
    route_class=APIRouteWrapper, dependencies=[Depends(verify_access_token)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@router.get("/api/file_upload_reports")
def get_file_upload_data(
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
    Retrieve file upload reports.

    This endpoint provides a detailed report of uploaded files, including filtering, sorting,
    grouping, and aggregation options.
    """

    allowed_columns = fields.split(",") if fields else []
    sort_criteria = sort_by.split(",") if sort_by else []
    filter_conditions = json.loads(filters) if filters else {}
    aggregate_conditions = json.loads(aggregate) if aggregate else {}
    group_by_conditions = json.loads(group_by) if group_by else {}

    collection = "file_upload_reports"

    if download_file_type:
        data, _ = db.get_data_from_table(
            collection,
            ["*.*"],
            filter_conditions,
            search,
            sort_by,
            page,
            per_page,
            aggregate,
            group_by,
        )
        return db.export_as_file(
            data=data, file_type=download_file_type, file_name=collection
        )

    if allowed_columns:
        data, metadata = db.get_data_from_table(
            collection,
            allowed_columns,
            filter_conditions,
            search,
            sort_criteria,
            page,
            per_page,
            aggregate_conditions,
            group_by_conditions,
        )
        return make_success_response(
            data=data,
            message="File Upload Data retrieved successfully",
            metadata=metadata,
        )
    return make_success_response(
        data=[], message="File Upload Data not found", metadata=[]
    )
