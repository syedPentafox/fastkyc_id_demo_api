from datetime import datetime, timedelta
from importlib import metadata
from typing import Optional
from unittest import result
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
import logging

from fastapi.params import Depends, Query
from numpy import select
from requests import Session
from orm_model.core_models import AepsFraudIncident, CreditCardFraudIncident, DematFraudIncident, EmailFraudIncident, EwalletFraudIncident, I4CRequest, InternetBankingFraudIncident, UpiFraudIncidents, VishingFraudIncident, get_db
from response_models.i4c_request_models import I4CRequestModel
from response_models.response_models import make_success_response
from routers import i4c_request
from utils.authentication import verify_access_token
from utils.custom_class import APIRouteWrapper
from utils.db_connection import db
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json

from sqlalchemy import Table, MetaData, select, and_
from sqlalchemy import Date, MetaData, Numeric, String, Table, and_, case, cast, func, literal, literal_column, text, union_all

metadata = MetaData()

router = APIRouter(
    route_class=APIRouteWrapper #,dependencies=[Depends(verify_access_token)]
)


@router.get("/ncrp/api/dashboard/count", tags=["Dashboard"])
def get_dashboard_counts(
    period: str = Query("today", enum=["today", "week", "month", "year"]),
    db: Session = Depends(get_db)
):
    now = datetime.now()

    if period == "today":
        start_date = datetime(now.year, now.month, now.day)
    elif period == "week":
        start_date = now - timedelta(days=now.weekday())
        start_date = datetime(start_date.year, start_date.month, start_date.day)
    elif period == "month":
        start_date = datetime(now.year, now.month, 1)
    elif period == "year":
        start_date = datetime(now.year, 1, 1)

    # ---- i4c_request counts ----
    base_query = db.query(I4CRequest).filter(I4CRequest.received_dt >= start_date, I4CRequest.msg_type == "REQ")

    total = base_query.count()
    total_not_read = base_query.filter(
        (I4CRequest.status.is_(None)) | (I4CRequest.status.notin_(["R", "P"]))
    ).count()
    total_read = base_query.filter(I4CRequest.status == "R").count()
    total_processed = base_query.filter(I4CRequest.status == "P").count()

  

    data = {
        "total": total,
        "not_read": total_not_read,
        "read": total_read,
        "processed": total_processed
    }

    return make_success_response(data=data, metadata={"period": period}, message="Dashboard counts fetched successfully")


FRAUD_MODELS = {
    "upi_fraud_incidents": UpiFraudIncidents,
    "ewallet_fraud_incidents": EwalletFraudIncident,
    "aeps_fraud_incidents": AepsFraudIncident,
    "credit_card_fraud_incidents": CreditCardFraudIncident,
    "demat_fraud_incidents": DematFraudIncident,
    "email_fraud_incidents": EmailFraudIncident,
    "internet_banking_fraud_incidents": InternetBankingFraudIncident,
    "vishing_fraud_incidents": VishingFraudIncident,
}


@router.get("/ncrp/api/dashboard/{collection}/count")
def get_fraud_status_by_collection(collection: str, db: Session = Depends(get_db)):
    model = FRAUD_MODELS.get(collection.lower())
    if not model:
        raise HTTPException(status_code=404, detail=f"Collection '{collection}' not found")

    validity_case = case(
        (model.is_valid == 1, "valid"),
        else_="invalid"
    )

    query = (
        db.query(
            model.mode_of_payment.label("mode"),
            model.status.label("status"),
            validity_case.label("validity"),
            func.count().label("count")
        )
        .filter(model.mode_of_payment.in_(["CREDIT", "DEBIT"]))
        .group_by(model.mode_of_payment, model.status, validity_case)
        .all()
    )

    result = {}
    # intermediate totals for valid/invalid
    totals = {}

    for row in query:
        mode = row.mode
        status = row.status or "Unknown"
        validity = row.validity
        count = row.count

        if mode not in result:
            result[mode] = {}
            totals[mode] = {"total_valid_count": 0, "total_invalid_count": 0}

        # for each status, sum counts
        if status not in result[mode]:
            result[mode][status] = 0
        result[mode][status] += count

        # add to totals
        if validity == "valid":
            totals[mode]["total_valid_count"] += count
        else:
            totals[mode]["total_invalid_count"] += count

    # merge totals into result
    for mode in totals:
        result[mode].update(totals[mode])

    return make_success_response(data=result, message="Fraud status fetched successfully")


@router.get("/ncrp/api/i4c-request/sub-category/count", tags=["I4C Request"])
def get_i4c_request_sub_category_count(db: Session = Depends(get_db)):
    sub_category_expr = func.json_value(I4CRequest.request, literal_column("'$.sub_category'"))

    result = (
        db.query(
            sub_category_expr.label("sub_category"),
            I4CRequest.status,
            func.count().label("count")
        )
        .filter(I4CRequest.msg_type == "REQ")
        .group_by(sub_category_expr, I4CRequest.status)
        .all()
    )

    status_map = {"N": "not_read", "R": "read", "P": "processed"}

    counts_dict = {"not_read": {}, "read": {}, "processed": {}}

    for row in result:
        sub_cat = row.sub_category or "UNKNOWN"
        status_label = status_map.get(row.status, "UNKNOWN")
        counts_dict[status_label][sub_cat] = row.count

    return make_success_response(
        data=counts_dict,
        message="Sub-category counts fetched successfully"
    )

@router.get("/ncrp/api/i4c-request/sub-category/list", tags=["I4C Request"])
def get_i4c_request_sub_category_list(db: Session = Depends(get_db)):
    sub_category_expr = func.json_value(I4CRequest.request, literal_column("'$.sub_category'"))
    result = (
        db.query(
            sub_category_expr.label("sub_category")
        )
        .filter(I4CRequest.msg_type == "REQ")
        .group_by(sub_category_expr)
        .all()
    )

    return make_success_response(
        data=[row.sub_category for row in result],
        message="Sub-category list fetched successfully"
    )

@router.get("/ncrp/api/i4c-request/sub-category/total", tags=["I4C Request"])
def get_i4c_request_sub_total(db: Session = Depends(get_db)):
    sub_category_expr = func.json_value(I4CRequest.request, literal_column("'$.sub_category'"))
    result = (
        db.query(
            sub_category_expr.label("sub_category"),
            func.count().label("count")
        )
        .filter(I4CRequest.msg_type == "REQ")
        .group_by(sub_category_expr)
        .all()
    )

    return make_success_response(
        data=[{"sub_category": row.sub_category, "count": row.count} for row in result],
        message="Sub-category totals fetched successfully"
    )

# List of fraud tables
INCIDENT_TABLES = [
    "upi_fraud_incidents",
    "aeps_fraud_incidents",
    "credit_card_fraud_incidents",
    "internet_banking_fraud_incidents",
    "demat_fraud_incidents",
    "email_fraud_incidents",
    "vishing_fraud_incidents",
    "ewallet_fraud_incidents",
]

FIELDS = [
    "ack_no",
    "job_id",
    "amount",
    "rrn",
    "transaction_date",
    "transaction_time",
    "disputed_amount",
    "layer",
    "received_dt",
    "mode_of_payment",
    "is_valid",
    "status",
]

def get_all_complaints_from_db(db: Session):
    results = []

    # --- 1) Fetch from fraud incident tables ---
    for table_name in INCIDENT_TABLES:
        table = Table(table_name, metadata, autoload_with=db.bind)
        cols = [getattr(table.c, f) for f in FIELDS if f in table.c]

        if not cols:
            continue  # skip tables with no matching columns

        stmt = select(*cols)
        rows = db.execute(stmt).fetchall()

        for row in rows:
            row_dict = {f: row._mapping.get(f) for f in FIELDS}
            results.append(row_dict)

    # --- 2) Fetch from i4c_request table ---
    i4c_table = Table("i4c_request", metadata, autoload_with=db.bind)
    stmt = select(i4c_table).where(
        and_(
            i4c_table.c.msg_type == "REQ",
            i4c_table.c.status == "N"
        )
    )
    rows = db.execute(stmt).fetchall()

    for row in rows:
        try:
            req_json = json.loads(row.request)
            incident = req_json.get("instrument", {}).get("incidents", [{}])[0]

            row_dict = {
                "ack_no": row.ack_no or req_json.get("acknowledgement_no"),
                "job_id": row.job_id,
                "amount": incident.get("amount"),
                "rrn": incident.get("rrn"),
                "transaction_date": incident.get("transaction_date"),
                "transaction_time": incident.get("transaction_time"),
                "disputed_amount": incident.get("disputed_amount"),
                "layer": incident.get("layer"),
                "received_dt": row.received_dt,
                "mode_of_payment": req_json.get("instrument", {}).get("mode_of_payment"),
                "is_valid": None,
                "status": "pending"
            }
        except Exception:
            # fallback if JSON is malformed
            row_dict = {f: None for f in FIELDS}
            row_dict["ack_no"] = row.ack_no
            row_dict["job_id"] = row.job_id
            row_dict["status"] = "pending"

        results.append(row_dict)

    return results


@router.get("/ncrp/api/complaints/all", tags=["Dashboard"])
def get_all_complaints(
    search: Optional[str] = Query(None),
    from_date: Optional[datetime] = Query(None),
    to_date: Optional[datetime] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    results = get_all_complaints_from_db(db)

    # --- Apply search filter ---
    if search:
        search_lower = search.lower()
        results = [
            row for row in results
            if any(
                search_lower in str(value).lower()
                for value in row.values() if value is not None
            )
        ]

    # --- Apply date filter ---
    if from_date or to_date:
        results = [
            row for row in results
            if row.get("received_dt")
            and ((from_date is None or row["received_dt"] >= from_date)
                 and (to_date is None or row["received_dt"] <= to_date))
        ]

    # --- Pagination ---
    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_results = results[start:end]

    return make_success_response(
        data=paginated_results,
        metadata={
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size,
        }
    )
