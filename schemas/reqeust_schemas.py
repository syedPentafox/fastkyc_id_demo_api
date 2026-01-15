from enum import Enum
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional

class ApiType(str, Enum):
    normal = "normal"
    pooling = "pooling"
    redirects = "redirects"

class ApiItem(BaseModel):
    id: int
    order: int
    api_type: ApiType = ApiType.normal

     # ---- Polling fields ----
    poll_interval: Optional[int] = None
    poll_max_attempts: Optional[int] = None
    poll_success_path: Optional[str] = None
    poll_success_value: Optional[str] = None

    # ---- Conditional fields ----
    is_conditional: bool = False
    condition_field: Optional[str] = None
    condition_value: Optional[str] = None

    @field_validator("order")
    @classmethod
    def order_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("order must be >= 1")
        return v

    @field_validator("poll_interval")
    @classmethod
    def validate_poll_interval(cls, v):
        if v is not None and v > 15:
            raise ValueError("poll_interval cannot be more than 15 seconds")
        return v


    @field_validator("poll_max_attempts")
    @classmethod
    def validate_poll_max_attempts(cls, v):
        if v is not None and v > 45:
            raise ValueError("poll_max_attempts cannot be more than 45")
        return v


class FeatureFlowRequest(BaseModel):
    name: str = Field(..., min_length=2)
    desc: str | None = None
    apis: List[ApiItem]

    @field_validator("apis")
    @classmethod
    def at_least_one_api(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one API must be provided")
        return v
