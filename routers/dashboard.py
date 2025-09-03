from datetime import datetime, timedelta
from unittest import result
from fastapi import APIRouter, HTTPException, Request, BackgroundTasks
import logging

from fastapi.params import Depends, Query
from requests import Session
from orm_model.core_models import AepsFraudIncident, CreditCardFraudIncident, DematFraudIncident, EmailFraudIncident, EwalletFraudIncident, I4CRequest, InternetBankingFraudIncident, UpiFraudIncidents, VishingFraudIncident, get_db
from response_models.i4c_request_models import I4CRequestModel
from response_models.response_models import make_success_response
from utils.authentication import verify_access_token
from utils.custom_class import APIRouteWrapper
from utils.db_connection import db
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json
from sqlalchemy import case, func, literal_column, text


router = APIRouter(
    route_class=APIRouteWrapper#,dependencies=[Depends(verify_access_token)]
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