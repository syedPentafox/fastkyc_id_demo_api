
from dotenv.main import logger
import uuid
import json
import os
from datetime import datetime
from fastapi import APIRouter, Depends, Body, HTTPException, Request
from sqlalchemy.orm import Session

from utils.db_util import DatabaseHandler
from utils.journey_auth import authenticate_journey_user
from response_models.response_models import make_success_response
from utils.error_handler import error_failure_response
from orm_model.core_models import (
    ActiveFlow, FlowFeatureMap, FeatureFlow, FeatureApiDependency, 
    FeatureMaster, FieldMaster, JourneyLog, ApiRequiredField
)
from utils.fastkyc_connector import FastKYCConnector
from response_models.journey_models import (
    JourneyState, FormUI, RedirectUI, PollingUI, MessageUI, UIActionType
)

router = APIRouter()
db = DatabaseHandler()

def get_current_step_config(session: Session, active_flow: ActiveFlow):
    """
    Locates the current FeatureFlow (Step) and the current Feature (API) 
    that the user is supposed to be on.
    """
    # 1. Find FlowFeatureMap for current_step
    current_map = (
        session.query(FlowFeatureMap)
        .filter(FlowFeatureMap.flow_id == active_flow.flow_id)
        .filter(FlowFeatureMap.execution_order == active_flow.current_step)
        .first()
    )
    
    if not current_map:
        return None, None
        
    ff_id = current_map.feature_id
    
    # 2. Find FeatureApiDependency
    if not active_flow.current_api_id:
        # Get first API in this Feature Flow
        start_dep = (
            session.query(FeatureApiDependency)
            .filter(FeatureApiDependency.feature_id == ff_id)
            .order_by(FeatureApiDependency.execution_order)
            .first()
        )
        return current_map, start_dep
    else:
        # Get the specific API
        return current_map, session.query(FeatureApiDependency).filter(
            FeatureApiDependency.feature_id == ff_id,
            FeatureApiDependency.api_id == active_flow.current_api_id
        ).first()

def get_form_fields_for_feature(session: Session, feature_id: int):
    """
    Helper to fetch and format form fields for a feature
    """
    field_mappings = (
        session.query(ApiRequiredField, FieldMaster)
        .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
        .filter(ApiRequiredField.api_id == feature_id)
        .all()
    )
    
    form_fields = []
    for mapping, field in field_mappings:
        f_dict = {}
        for col in field.__table__.columns:
            val = getattr(field, col.name)
            if isinstance(val, datetime):
                val = val.isoformat()
            f_dict[col.name] = val
        f_dict['is_mandatory'] = mapping.is_mandatory
        # Use key_name if mapped
        if mapping.key_name:
             f_dict['field'] = mapping.key_name
             f_dict['original_field'] = field.field # keep ref
        form_fields.append(f_dict)
    
    return form_fields

def execute_polling_check(session: Session, active_flow: ActiveFlow, target_api_dep: FeatureApiDependency, customer_id: str):
    """
    Checks status of a polling API to determine if the user can proceed to the next step.
    
    Logic:
    1. Fetches the client_id for this session from journey_state.
    2. Calls the polling feature API (FastKYC) with the client_id.
    3. Analyzes the API response:
       - SUCCESS: 
         - Checks deeply for "is_completed" flag or "inner status" ("client_initiated", "pending").
         - If truly complete -> Update State -> Advance Flow -> Return None.
         - If pending -> Return PollingUI (Keep polling).
       - FAILED: Return Error UI.
       - PENDING/Other: Return PollingUI.
       
    Returns:
    - PollingUI/MessageUI: If the frontend should show a specific UI.
    - None: If the state has successfully advanced and the caller should re-resolve the state.
    """
    feature = session.query(FeatureMaster).filter(FeatureMaster.id == target_api_dep.api_id).first()
    journey_state = active_flow.journey_state or {}
    client_id = journey_state.get("client_id")
    
    if not client_id:
        # Should not happen if flow logic is correct, but safe fallback
        return PollingUI(message="Initializing verification...")

    connector = FastKYCConnector(session, customer_id)
    input_data = {"client_id": client_id}
    
    try:
        result = connector.execute_feature(feature, input_data)
        status = result.get("status")
        
        if status == "SUCCESS" or status == "success":
            # Check for Inner Status (Deep Check)
            # The API might be successful (200 OK) but the task is still processing.
            result_data = result.get("data", {})
            
            is_completed = result_data.get("is_completed")
            inner_status = result_data.get("status")

            # Logic: If explicitly incomplete OR status keywords match pending -> Keep Polling
            if (is_completed is False) or (inner_status in ["client_initiated", "pending", "processing"]):
                 return PollingUI(
                    client_id=client_id, 
                    feature_id=feature.id, 
                    message="Verification in progress..."
                )

            # Polling Complete!
            # Extract updated data (e.g new client_id or result artifacts)
            new_client_id = result_data.get("client_id") or result.get("client_id")
            if new_client_id:
                journey_state["client_id"] = new_client_id
                active_flow.journey_state = journey_state
            
            # Advance Flow to Next API or Step
            advance_flow_state(session, active_flow, target_api_dep)
            return None # Signal to caller: State Changed, Re-Resolve!
            
        elif status == "FAILED" or status == "failed":
             return MessageUI(status="FAILED", message=result.get("message", "Verification Failed"))
        else:
            return PollingUI(
                client_id=client_id, 
                feature_id=feature.id, 
                message="Verification in progress..."
            )
            
    except Exception as e:
        print(f"Polling Exception: {e}")
        return PollingUI(message="Retrying connection...")

def advance_flow_state(session: Session, active_flow: ActiveFlow, current_dep: FeatureApiDependency):
    """
    Moves active_flow to next API or Next Step
    """
    # Find all APIs in current step
    apis = (
        session.query(FeatureApiDependency)
        .filter(FeatureApiDependency.feature_id == current_dep.feature_id)
        .order_by(FeatureApiDependency.execution_order)
        .all()
    )
    
    # Find current index
    current_idx = -1
    for i, api in enumerate(apis):
        if api.api_id == current_dep.api_id:
            current_idx = i
            break
            
    if current_idx + 1 < len(apis):
        # Move to next API in same step
        next_api = apis[current_idx + 1]
        active_flow.current_api_id = next_api.api_id
    else:
        # Move to Next Step
        active_flow.current_step += 1
        active_flow.current_api_id = 0 # Reset
        
    session.commit()


def resolve_journey_state(session: Session, active_flow: ActiveFlow, customer_id: str = None, step_response_data: dict = None) -> JourneyState:
    """
    Pure function to determine current Journey State based on DB
    """
    base_state = {
        "flow_id": active_flow.id,
        "status": active_flow.status,
        "current_step": active_flow.current_step or 1,
        "total_steps": 0, # TODO: Calculate total steps if needed
        "step_response_data": step_response_data
    }

    if active_flow.status == 'completed':
        return JourneyState(**base_state, ui=MessageUI(status="COMPLETED", message="Journey Completed"))

    current_map, target_api_dep = get_current_step_config(session, active_flow)
    
    if not current_map or not target_api_dep:
         # End of flow or invalid config
        active_flow.status = 'completed'
        session.commit()
        base_state['status'] = 'completed' # Update base_state
        return JourneyState(**base_state, ui=MessageUI(status="COMPLETED", message="Journey Completed"))
    print("target_api_dep", target_api_dep)
    # CASE 1: API Type is POLLING
    # We must check the status of the external task without user input.
    if target_api_dep.api_type == 'pooling':
        # Execute the check side-effect
        ui_result = execute_polling_check(session, active_flow, target_api_dep, customer_id)
        
        # If check returned None, it means it SUCCEEDED and ADVANCED state.
        # We must recursively call ourselves to see what the *new* state is.
        if ui_result is None:
             return resolve_journey_state(session, active_flow, customer_id, step_response_data)
        
        # Otherwise, return the PollingUI (or Error) to the frontend
        return JourneyState(**base_state, ui=ui_result)

    # CASE 2: API Type is FORM or REDIRECT (Initial load)
    # Return the UI definition so the frontend can render the inputs.
    feature = session.query(FeatureMaster).filter(FeatureMaster.id == target_api_dep.api_id).first()
    form_fields = get_form_fields_for_feature(session, feature.id)
    
    return JourneyState(
        **base_state, 
        ui=FormUI(
            feature_id=feature.id,
            feature_name=feature.feature,
            title=feature.title,
            description=feature.feature_description,
            form_fields=form_fields
        )
    )

@router.get("/journey/state", response_model=JourneyState, tags=['journey'])
def get_journey_state(
    auth: dict = Depends(authenticate_journey_user)
):
    active_flow_id = auth.get("flow_id")
    customer_id = auth.get("customer_id")
    
    with db.Session() as session:
        flow = session.query(ActiveFlow).filter(ActiveFlow.id == active_flow_id).first()
        if not flow:
            return error_failure_response("Flow not found", 404)
            
        state = resolve_journey_state(session, flow, customer_id)
        return state 


@router.post("/journey/next", response_model=JourneyState, tags=['journey'])
def execute_journey_step(
    payload: dict = Body(...),
    auth: dict = Depends(authenticate_journey_user)
):
    active_flow_id = auth.get("flow_id")
    customer_id = auth.get("customer_id")
    input_data = payload

    with db.Session() as session:
        flow = session.query(ActiveFlow).filter(ActiveFlow.id == active_flow_id).first()
        if not flow:
             return error_failure_response("Flow not found", 404)
        
        # 1. Get Current Config
        current_map, target_api_dep = get_current_step_config(session, flow)
        if not current_map or not target_api_dep:
             return error_failure_response("Invalid Flow State", 400)

        feature = session.query(FeatureMaster).filter(FeatureMaster.id == target_api_dep.api_id).first()
        print("feature from table. ---->", feature)
        # 2. Prepare Data (Dependency Injection)
        journey_state = flow.journey_state or {}
        final_data = input_data.copy()
  
        if "client_id" in journey_state and "client_id" not in final_data:
             final_data["client_id"] = journey_state["client_id"]
        
        # 3. Validation (Optional: Check mandatory fields against get_form_fields_for_feature)
      

        # 4. Execute Feature
        connector = FastKYCConnector(session, customer_id)
        
        # Handle Redirect Setup
        if feature.request and "redirect_url" in feature.request:
                redirect_url = os.getenv("JOURNEY_CALLBACK_URL")
                if redirect_url:
                    final_data["redirect_url"] = redirect_url
                    final_data["state"] = str(uuid.uuid4())

        try:
            api_result = connector.execute_feature(feature, final_data)
        except Exception as e:
             return error_failure_response(f"Execution Error: {str(e)}", 500)

        status = api_result.get("status", "UNKNOWN")
        success = api_result.get("success", False) or status in ["SUCCESS", "success"]
        
        # Deep check for success if needed (matches polling logic)
        result_data = api_result.get("data", {})
        if success and isinstance(result_data, dict):
             is_completed = result_data.get("is_completed")
             inner_status = result_data.get("status")
             if (is_completed is False) or (inner_status in ["client_initiated", "pending", "processing"]):
                  success = False
                  if inner_status == "client_initiated":
                       return error_failure_response("Verification pending completion", 400)

        
        # Log
        log = JourneyLog(
            active_flow_id=flow.id,
            feature_id=current_map.feature_id,
            api_id=feature.id,
            status=status,
            request_log=json.dumps(final_data),
            response_log=json.dumps(api_result),
            created_at=datetime.now()
        )
        session.add(log)
        
        if not success:
             return error_failure_response(api_result.get("message", "Step Failed"), 400)
             
        # 6. Success Handling & State Transitions
        
        # 6a. Extract and save Client ID
        # Many APIs return a client_id that is needed for subsequent steps.
        data = api_result.get("data", {})
        client_id = None
        if isinstance(data, dict):
             client_id = data.get("client_id")
        
        if client_id:
             journey_state["client_id"] = client_id
             flow.journey_state = journey_state
             
        # 6b. Handle Redirects (Special Case)
        # If this API was a REDIRECT type, we:
        # 1. Advance the flow immediately (Assuming user will go to the redirect).
        # 2. Return a RedirectUI to the frontend.
        # 3. The next time frontend calls /state, it will hit the *next* API (usually Polling).
        if target_api_dep.api_type == "redirects":
             redirect_url = data.get("url")
             if not redirect_url:
                  return error_failure_response("Redirect URL missing from provider", 500)
             
             # Store url mainly for recovery/logging
             journey_state["redirect_url"] = redirect_url
             flow.journey_state = journey_state
             
             # Advance State immediately
             advance_flow_state(session, flow, target_api_dep)
             
             base_state = {
                "flow_id": flow.id,
                "status": flow.status,
                "current_step": flow.current_step,
                "total_steps": 0
             }
             return JourneyState(
                 **base_state,
                 ui=RedirectUI(url=redirect_url)
             )
        
        # 6c. Standard Success -> Advance
        # For Form APIs, success means we just move to the next thing.
        advance_flow_state(session, flow, target_api_dep)
        
        # Return NEXT state
        # We recursively call resolve_journey_state to see what happens next 
        # (e.g. might immediately execute a polling check or return the next form)
        return resolve_journey_state(session, flow, customer_id, step_response_data=api_result.get("data", {}))

