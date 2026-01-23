from pydantic import BaseModel, Field
from typing import List, Optional, Union, Dict, Any, Literal
from enum import Enum

class UIActionType(str, Enum):
    FORM = "FORM"
    REDIRECT = "REDIRECT"
    POLLING = "POLLING"
    MESSAGE = "MESSAGE"
    NONE = "NONE"

class BaseUI(BaseModel):
    type: UIActionType
    title: Optional[str] = None
    description: Optional[str] = None

class FormUI(BaseUI):
    type: Literal[UIActionType.FORM] = UIActionType.FORM
    feature_id: int
    feature_name: str
    form_fields: List[Dict[str, Any]]

class RedirectUI(BaseUI):
    type: Literal[UIActionType.REDIRECT] = UIActionType.REDIRECT
    url: str
    poll_info: Optional[Dict[str, Any]] = None

class PollingUI(BaseUI):
    type: Literal[UIActionType.POLLING] = UIActionType.POLLING
    client_id: Optional[str] = None
    feature_id: Optional[int] = None
    message: str = "Processing..."

class MessageUI(BaseUI):
    type: Literal[UIActionType.MESSAGE] = UIActionType.MESSAGE
    status: str = "SUCCESS" 
    message: str
    data: Optional[Any] = None

class JourneyState(BaseModel):
    flow_id: str
    status: str # active, completed, etc.
    current_step: int
    total_steps: int = 0
    ui: Union[FormUI, RedirectUI, PollingUI, MessageUI]
    step_response_data: Optional[Dict[str, Any]] = None
