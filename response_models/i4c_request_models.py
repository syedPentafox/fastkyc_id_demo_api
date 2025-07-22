from pydantic import BaseModel
from typing import List, Optional

class IncidentModel(BaseModel):
    rrn: str
    amount: float
    transaction_date: str
    transaction_time: str
    disputed_amount: float
    layer: int

class InstrumentModel(BaseModel):
    requestor: str
    payer_bank: str
    mode_of_payment: str
    payer_bank_code: int
    payer_account_number: str
    payer_mobile_number: str
    state: str
    district: str
    transaction_type: Optional[str] = ""
    incidents: List[IncidentModel]

class PayloadModel(BaseModel):
    acknowledgement_no: str
    sub_category: str
    instrument: InstrumentModel

class I4CRequestModel(BaseModel):
    payload: PayloadModel
    ack_no: str
    job_id: str
    status: str
    msg_type: str
    received_dt: str
