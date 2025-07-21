from fastapi import Query, APIRouter, Depends
from utils.db_connection import db
from fastapi.encoders import jsonable_encoder
import logging
from utils.custom_class import APIRouteWrapper
from sqlalchemy import text
from response_models.response_models import make_failure_response, make_success_response
from math import ceil
from router_helper.report_helper import (
    extract_column_names,
    generate_report_column_title_map,
)
import json
from utils.authentication import verify_access_token

router = APIRouter(
    route_class=APIRouteWrapper, dependencies=[Depends(verify_access_token)]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@router.get("/api/reports/{report_name}", tags=["Reports"])
def query_reports(
    report_name: str,
    page: int = 1,
    per_page: int = Query(10, ge=1),
    filters: str = None,
    search: str = None,
    sort_by: str = None,
    summary: str = None,
    export_as_file: bool = False,
):
    """
    Retrieve a report with advanced filtering, sorting, and pagination options.

    This endpoint retrieves data for a specified report based on various query parameters,
    allowing for flexible filtering, sorting, searching, and exporting.
    """
    get_report_meta_columns_query = text(
        f"""select static_select, dynamic_select, where_clause, group_by, order_by, filters
        FROM reporting where api = '{report_name}' limit 1"""
    )
    report_meta_columns = db.execute_query(get_report_meta_columns_query)
    if not report_meta_columns:
        return make_failure_response(message="No report exists with this name")
    report_meta_data = report_meta_columns[0]._asdict()

    """dynamically generating columns and attaching it to the static columns"""
    select_statement = report_meta_data["static_select"]
    dynamic_columns_query = text(f"""{report_meta_data["dynamic_select"]}""")
    dynamic_columns_result = db.execute_query(dynamic_columns_query)
    if dynamic_columns_result:
        dynamic_columns = dynamic_columns_result[0][0]
        select_statement = select_statement.replace(
            "{dynamic_columns}", dynamic_columns
        )

    """assembling the query from select, where, group by and order by clauses"""
    where_clause = report_meta_data["where_clause"]
    group_by = report_meta_data["group_by"]
    order_by = report_meta_data["order_by"]
    assembled_query_clauses = [
        select_statement,
        where_clause,
        group_by if group_by else "",
        order_by if order_by else "",
    ]
    assembled_query = " ".join(assembled_query_clauses)

    """recursively finding and replacing the placeholders with filters"""
    find_replace_map = json.loads(filters) if filters else {}
    for find_text, replace_text in find_replace_map.items():
        if isinstance(replace_text, str):
            replace_text = f"'{replace_text}'"
        elif isinstance(replace_text, list):
            replace_text = (
                f"({', '.join(str(value).upper() for value in replace_text)})"
            )
        assembled_query = assembled_query.replace(
            f"""{{{find_text}}}""", str(replace_text)
        )
    final_query = f"""with {report_name}_tmp as ({assembled_query}) \n select * from {report_name}_tmp"""

    """getting the columns names from the select query"""
    column_names = extract_column_names(select_statement)

    """applying flat search on all the column values after casted as string"""
    flat_search = []
    if search:
        for column in column_names:
            flat_search.append(f"""(CAST("{column}" AS TEXT) LIKE '%{search}%')""")
        flat_search_phrase = " OR ".join(flat_search)
        final_query = f"""{final_query} where {flat_search_phrase}"""

    """getting total count along with including the columns for aggregating in case the
    summary is requested"""
    if summary:
        summary = f"""select count(1) as total_rows,
        {",".join([f"sum({field}) as {field}" for field in summary.split(",")])}
        from {report_name}_tmp """
    else:
        summary = f"""select count(1) as total_rows from {report_name}_tmp """

    """getting total count of records"""
    total_count_query_result = db.execute_query(
        text(f"""{final_query.replace(f"select * from {report_name}_tmp", summary)}""")
    )
    total_records = (
        total_count_query_result[0]._asdict().get("total_rows")
        if total_count_query_result
        else 0
    )
    report_summary = (
        {
            key: value
            for key, value in total_count_query_result[0]._asdict().items()
            if key != "total_rows"
        }
        if total_count_query_result
        else {}
    )

    """sort by has to happen after getting the total since it will result in error when
    you use order by in a grouping or aggregating i.e, count(1)"""
    if sort_by:
        final_query = final_query + " order by " + sort_by

    """executing the result with pagination"""
    if export_as_file:
        """exporting should get all the data into the file so keeping it to -1 which will
        not enable the pagination"""
        page = -1
    total_pages = ceil(total_records / per_page)
    offset = (page - 1) * per_page
    if page > 0:
        final_query = final_query + f""" LIMIT {per_page} OFFSET {offset}"""

    """fetching the results from the database"""
    final_query_result = db.execute_query(text(final_query))
    result_as_json = (
        [record._asdict() for record in final_query_result if record]
        if final_query_result
        else []
    )

    if export_as_file:
        return db.export_as_file(
            data=result_as_json,
            file_type="xlsx",
            file_name=report_name,
            summary={
                key.replace("_", " ").title(): value
                for key, value in report_summary.items()
            },
            custom_headers=generate_report_column_title_map(column_names),
        )

    """constructing the header map which will say , replace the query result column with
    this label"""
    headers = []
    for index, column in enumerate(column_names, start=1):
        headers.append(
            {"id": index, "field": column, "label": column.replace("_", " ").title()}
        )

    """consolidating the report data, metadata and status message"""
    metadata = {
        "page": page,
        "per_page": per_page,
        "total_number_of_page": total_pages,
        "headers": headers,
        "records": total_records,
        "summary": jsonable_encoder(report_summary),
        "filters": json.loads(report_meta_data["filters"]),
    }
    return make_success_response(
        data=result_as_json,
        message=f"{report_name} retrived successful",
        metadata=metadata,
    )
