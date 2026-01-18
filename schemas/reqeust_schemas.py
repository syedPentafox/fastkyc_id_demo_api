from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Optional
import re

class ApiType(str, Enum):
    default = "default"
    pooling = "pooling"
    redirects = "redirects"

class ApiItem(BaseModel):
    id: int
    order: int
    api_type: ApiType = ApiType.default

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

class FlowItem(BaseModel):
    id: int
    order: Optional[int] = None

    @field_validator("order")
    @classmethod
    def order_must_be_positive(cls, v):
        if v is not None and v <= 0:
            raise ValueError("Order must be >= 1")
        return v

class FlowGenerationRequest(BaseModel):
    name: str = Field(..., min_length=2)
    desc: Optional[str] = None
    feature_flow: List[FlowItem]

    @field_validator("feature_flow")
    @classmethod
    def validate_flow(cls, v):
        if not v or len(v) == 0:
            raise ValueError("At least one feature flow is required")
        
        # Check order presence
        has_order = any(item.order is not None for item in v)
        all_have_order = all(item.order is not None for item in v)
        none_have_order = all(item.order is None for item in v)

        if not (all_have_order or none_have_order):
             raise ValueError("All items must either have an order or no order (cannot be mixed)")

        if all_have_order:
            # Sort by order to check sequence
            sorted_flows = sorted(v, key=lambda x: x.order)
            for i, item in enumerate(sorted_flows):
                expected_order = i + 1
                if item.order != expected_order:
                    raise ValueError(f"Order sequence broken. Expected {expected_order}, got {item.order}")
            return sorted_flows
            
        else: 
            # Auto-assign order based on list index (chronological as received)
            for i, item in enumerate(v):
                item.order = i + 1
            return v

class EndCustomerDetails(BaseModel):
    name: str = Field(..., min_length=1)
    phone: Optional[str] = None
    email: Optional[str] = None
    additional_data: Optional[dict] = None

    # @model_validator(mode="after")
    # def validate_contact_info(self):
    #     if not self.phone or not self.email:
    #         raise ValueError("At least one contact method (phone or email) must be provided")
    #     return self

class FlowActivationRequest(BaseModel):
    flow_id: int
    end_customer_details: EndCustomerDetails
    expires: Optional[datetime] = None

