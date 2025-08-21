from fastapi import APIRouter, Request, BackgroundTasks
import logging
from response_models.i4c_request_models import I4CRequestModel
from utils.db_connection import db
router = APIRouter()
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
import json
from sqlalchemy import text



from background_jobs.i4c_request_job import i4c_request_job

#@router.post("/api/i4c-request", tags=["I4C Request"])
@router.get("/api/i4c-request")
#async def i4c_request(request_data: I4CRequestModel, request: Request, background_tasks: BackgroundTasks):
async def i4c_request(background_tasks:BackgroundTasks):
    out, _ = db.get_data_from_table(
        tbl_name="i4c_request",
        columns="*",
        #filters={"status_neq": "P", "msg_type_eq": "REQ", "job_id_eq": "KVB-79988661-d853-4c63-b1f2-f510f454273d"},
        filters={"status_neq": "P", "msg_type_eq": "REQ"},
        sort_by=["-job_id"],
        page=-1
    )

    for o in out:
        #db.execute_ddl(text(
        #    "insert into upi_fraud_transactions values ('a','a','a','a','a','a','a','a','a','06-08-25 12:30:45.123456','a')"
        #))
        #db.execute_ddl(text("insert into roles values (4,'test')"))
        #db.create_record('roles',{'id':5,'name':'test'})
        """db.create_record('upi_fraud_transactions', {
            'job_id': o['job_id'],
            'sub_category': o['request']['sub_category'],
            'requestor': o['request']['instrument']['requestor'],
            'payer_bank_code': o['request']['instrument']['payer_bank_code'],
            'mode_of_payment': o['request']['instrument']['mode_of_payment'],
            'payer_mobile_number': o['request']['instrument']['payer_mobile_number'],
            'payer_account_number': o['request']['instrument']['payer_account_number'],
            'state': o['request']['instrument']['state'],
            'district': o['request']['instrument']['district'],
            'received_dt': o['received_dt'] 
        })

        for i in o['instrument']['incidents']:
            db.create_record('upi_fraud_incidents', {
                'ack_no': o['ack_no'],
                'job_id': o['job_id'],
                'amount': i['amount'],
                'rrn': i['rrn'],
                'transaction_date': i['transaction_date'],
                'transaction_time': i['transaction_time'],
                'disputed_amount': i['disputed_amount'],
                'layer': i['layer']
            })"""

    for o in out:
        a = o
       # db.bulk_update_record('i4c_request', {'job_id': o['job_id']}, {'status': 'R'})
        logger.info('i4c_request entry start')
        logger.info(str(o))
        logger.info('i4c_request entry end')
        i4c_request_job(o)
        # background_tasks.add_task(i4c_request_job, o)
    logger.info(f"Received data from db : {str(out)}")
    #background_tasks.add_task(i4c_request_job,out)
    return out
