from datetime import datetime, timedelta
from fastapi import APIRouter, Request, BackgroundTasks
import logging

from fastapi.params import Depends, Query
from requests import Session
from orm_model.core_models import I4CRequest, UpiFraudIncidents, get_db
from response_models.i4c_request_models import I4CRequestModel
from response_models.response_models import make_success_response
from utils.authentication import verify_access_token
from utils.custom_class import APIRouteWrapper
from utils.db_connection import db
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json
from sqlalchemy import func, text


router = APIRouter(
    route_class=APIRouteWrapper,dependencies=[Depends(verify_access_token)]
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