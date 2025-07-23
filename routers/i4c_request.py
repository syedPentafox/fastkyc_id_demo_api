from fastapi import APIRouter, Request, BackgroundTasks
import logging
from response_models.i4c_request_models import I4CRequestModel

router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)



from background_jobs.i4c_request_job import i4c_request_job

@router.post("/api/i4c-request", tags=["I4C Request"])
async def i4c_request(request_data: I4CRequestModel, request: Request, background_tasks: BackgroundTasks):
    logger.info(f"Received I4C request: {request_data.json()}")
    background_tasks.add_task(i4c_request_job, request_data.json())
    return request_data
