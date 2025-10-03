from fastapi import APIRouter, Request, BackgroundTasks
import logging
import os
from response_models.i4c_request_models import I4CRequestModel
from utils.db_connection import db
router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json
from sqlalchemy import text
from fastapi.responses import FileResponse



from background_jobs.i4c_request_job import i4c_request_job
from fastapi_utilities import repeat_at, repeat_every

#@router.on_event("startup")
#@repeat_at(cron="0,15,30,45 * * * *")
#def repeat_fn():
#    logger.info("log from repeat_fn")

#@router.post("/api/i4c-request", tags=["I4C Request"])
@router.get("/api/i4c-request")
#async def i4c_request(request_data: I4CRequestModel, request: Request, background_tasks: BackgroundTasks):
#@router.on_event("startup")
#@repeat_every(seconds = 60 * 10)
async def i4c_request():
    out, _ = db.get_data_from_table(
        tbl_name="i4c_request",
        columns="*",
        filters={"status_eq": "N", "msg_type_eq": "REQ"},
        #filters={"msg_type_eq": "REQ", 'status_eq': 'N', "job_id_eq":"KVB-0013bdd9-de22-43be-9ee6-a66b18c22533"},
        #filters={"job_id_eq": "KVB-5f7af92e-6dfb-4d56-974f-5e7685178c22"},
        #filters={"job_id_eq": "KVB-57272284-15ff-4aeb-ad8a-6caa70c69948"},
        #filters={"job_id_eq": "KVB-6b4e9b19-169e-4ff9-8d6d-385d3e7c8307"},
        #filters={"status_eq": "N", "msg_type_eq": "REQ"},
        sort_by=["-job_id"],
        page=1
    )

    for o in out:
        logger.info('i4c_request entry start')
        logger.info(str(o))
        logger.info('i4c_request entry end')

        out1, __ = db.get_data_from_table(
            tbl_name="i4c_request",
            columns="*",
            filters={"job_id_eq": o['job_id'], "msg_type_eq": "RES"},
            sort_by=["-job_id"],
            page=1
        )

        if not out1:
            continue

        logger.info('out1')
        logger.info(out1)
        if out1[0]['request']['meta']['response_code'] == '00':
            logger.info(f'ack found for {o}')
            i4c_request_job(o)
        # background_tasks.add_task(i4c_request_job, o)
    logger.info(f"Received data from db : {str(out)}")
    #background_tasks.add_task(i4c_request_job,out)
    return out

@router.get("/ncrp/api/download-log")
async def download_log(filename: str):
    logs_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'logs'))
    file_path = os.path.join(logs_dir, filename)
    if not os.path.isfile(file_path):
        return {"error": "File not found"}
    return FileResponse(path=file_path, filename=filename, media_type='application/octet-stream')
