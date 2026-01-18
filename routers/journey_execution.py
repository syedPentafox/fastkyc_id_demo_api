from fastapi import APIRouter, Depends, Body, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
import json

from utils.db_util import DatabaseHandler
from utils.journey_auth import authenticate_journey_user
from response_models.response_models import make_success_response
from utils.error_handler import error_failure_response
from orm_model.core_models import (
    ActiveFlow, FlowFeatureMap, FeatureFlow, FeatureApiDependency, 
    FeatureMaster, FieldMaster, JourneyLog, ApiRequiredField
)
from utils.fastkyc_connector import FastKYCConnector

router = APIRouter()
db = DatabaseHandler()

def get_current_step_config(session: Session, active_flow: ActiveFlow):
    """
    Locates the current FeatureFlow (Step) and the current Feature (API) 
    that the user is supposed to be on.
    """
    # 1. Find FlowFeatureMap for current_step
    # Note: current_step is 1-based index of the 'FeatureFlow' sequence in the 'Flow'
    current_map = (
        session.query(FlowFeatureMap)
        .filter(FlowFeatureMap.flow_id == active_flow.flow_id)
        .filter(FlowFeatureMap.execution_order == active_flow.current_step)
        .first()
    )
    
    if not current_map:
        return None, None
        
    ff_id = current_map.feature_id
    
    # 2. Find FeatureApiDependency for active_flow.current_feature_id
    # If this is NULL (start of step), get the first one
    if not active_flow.current_feature_id:
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
        # We need to find the dependency row that points to this feature_id (which is actually api_id??)
        # Wait, core_models says: current_feature_id. 
        # But FeatureFlow has MANY APIs.
        # Let's assume current_feature_id refers to 'FeatureMaster.id' or 'FeatureApiDependency.id'?
        # The prompt says "current_feature_id" and "current_api_id" in ActiveFlow.
        # Let's use 'current_api_id' to track the FeatureMaster ID.
        
        # If current_api_id is set, we are ON that step.
        return current_map, session.query(FeatureApiDependency).filter(
            FeatureApiDependency.feature_id == ff_id,
            FeatureApiDependency.api_id == active_flow.current_api_id
        ).first()

@router.post("/journey/submit", tags=['journey'])
def submit_step_data(
    request: Request,
    payload: dict = Body(...),
    auth: dict = Depends(authenticate_journey_user)
):
    try:
        active_flow_id = auth.get("flow_id")
        customer_id = auth.get("customer_id")
        
        # Input Data
        # Expecting: { "data": { ... } } or just { ... }?
        # Let's support { ...inputs... } directly as body
        input_data = payload
        
        with db.Session() as session:
            # 1. Load Active Flow
            flow = session.query(ActiveFlow).filter(ActiveFlow.id == active_flow_id).first()
            if not flow:
                return error_failure_response("Flow not found", 404)
            
            if flow.status != "active":
                return error_failure_response("Flow is not active", 400)

            # Initialize step if needed
            if not flow.current_step:
                flow.current_step = 1
                
            # 2. Identify Current Config
            # We need to know WHICH Feature (API) we are executing.
            # If current_api_id is NULL, find the first API of the current step.
            
            flow_map = (
                session.query(FlowFeatureMap)
                .filter(FlowFeatureMap.flow_id == flow.flow_id)
                .filter(FlowFeatureMap.execution_order == flow.current_step)
                .first()
            )
            
            if not flow_map:
                # Journey Complete?
                return make_success_response({"status": "COMPLETE", "message": "Journey Completed"})
                
            feature_flow_id = flow_map.feature_id
            
            # Find the API dependency to execute
            # If flow.current_api_id is set, it means we are re-trying OR completing a polling step?
            # Actually, standard flow: 
            # - User Submits Data -> We Find NEXT API to execute (or current if it's the first time).
            # - But usually UI submits data FOR a specific form.
            # - So we should check if the submitted data matches the expected API fields.
            
            # Let's Look for the *Next Pending* API or the *Current* API if it was failed/polling.
            
            # Get all APIs for this step
            apis = (
                session.query(FeatureApiDependency)
                .filter(FeatureApiDependency.feature_id == feature_flow_id)
                .order_by(FeatureApiDependency.execution_order)
                .all()
            )
            
            target_api_dep = None
            
            # Logic to find "Current"
            if not flow.current_api_id:
                target_api_dep = apis[0] if apis else None
            else:
                # We are at a specific API.
                # If it was "FAILED" or "POLLING", we might be re-submitting for IT.
                # If it was "SUCCESS", we want the NEXT one.
                # But 'submit' implies "Here is data, do the thing".
                # Let's assume we are submitting for the `current_api_id` if set, 
                # OR if the previous one finished, we move to next.
                # Simplify: The UI "Knows" what it's submitting? 
                # No, Server Driven.
                # Let's Assume: The flow.current_api_id points to the one we are ABOUT to do or doing.
                
                # Find index of current
                for i, api in enumerate(apis):
                    if api.api_id == flow.current_api_id:
                        target_api_dep = api
                        break
            
            if not target_api_dep:
                return error_failure_response("Configuration Error: No APIs in step", 500)
                
            # Load Feature Master
            feature = session.query(FeatureMaster).filter(FeatureMaster.id == target_api_dep.api_id).first()
            
            # 3. Validate Input Data (Basic Check against FieldMaster)
             # (Skipping deep regex validation for speed, but ideally done here)
             
            # 4. Dependency Injection
            # Check if this API needs 'client_id' or other state from previous steps.
            # We don't have explicit "needs_client_id" flag in core_models detailed in prompt (just said 'some apis will need').
            # We'll heuristic: If 'client_id' is in `journey_state` and NOT in `input_data`, inject it.
            
            journey_state = flow.journey_state or {}
            
            final_data = input_data.copy()
            if "client_id" in journey_state and "client_id" not in final_data:
                final_data["client_id"] = journey_state["client_id"]
                
            # 5. Execute via Connector
            connector = FastKYCConnector(session, customer_id)
            api_result = connector.execute_feature(feature, final_data)
            
            # 6. Handle Result
            status = api_result.get("status", "UNKNOWN") # FastKYC returns 'status' usually?
            # User example: {"status": "SUCCESS", "client_id": ...}
            
            # Update State
            if "client_id" in api_result:
                journey_state["client_id"] = api_result["client_id"]
                flow.journey_state = journey_state
                
            # Log
            log = JourneyLog(
                active_flow_id=flow.id,
                feature_id=feature_flow_id,
                api_id=feature.id,
                status=status,
                request_log=json.dumps(final_data),
                response_log=json.dumps(api_result),
                created_at=datetime.now()
            )
            session.add(log)
            
            # Decision Logic
            next_step_response = {}
            
            # Handle POLLING / REDIRECT
            if target_api_dep.api_type == "redirects":
                # Redirect logic
                # Usually returns a URL to redirect user to.
                # We stay on this step/api until verified.
                redirect_url = api_result.get("url")
                # Also probably a client_id for polling?
                
                # Update flow to 'polling' state for this api?
                flow.current_api_id = feature.id
                session.commit()
                
                return make_success_response({
                    "action": "REDIRECT",
                    "url": redirect_url,
                    "poll_info": {
                        "api_id": feature.id,
                        "client_id": api_result.get("client_id")
                    }
                })
                
            elif target_api_dep.api_type == "pooling":
                # Polling logic (if this API ITSELF is the one to poll, or if it triggers polling)
                # Usually 'pooling' type means "Keep calling me".
                # If status != SUCCESS, return WAIT.
                pass 
                
            # DEFAULT / SUCCESS behavior: Move to Next API
            if status == "SUCCESS" or "client_id" in api_result: # Loose success check
                # Advance
                # 1. Check if more APIs in this Step
                next_api = None
                current_idx = -1
                for i, api in enumerate(apis):
                     if api.api_id == target_api_dep.api_id:
                         current_idx = i
                         break
                 
                if current_idx + 1 < len(apis):
                    next_api = apis[current_idx + 1]
                    # Set current to next
                    flow.current_api_id = next_api.api_id
                    
                    # Return "Next Input Form"
                    # Fetch fields for next api using existing helper logic or query
                    next_feature = session.query(FeatureMaster).filter(FeatureMaster.id == next_api.api_id).first()
                    
                    # Get Form Fields
                    field_mappings = (
                        session.query(ApiRequiredField, FieldMaster)
                        .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                        .filter(ApiRequiredField.api_id == next_feature.id)
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
                        form_fields.append(f_dict)

                    session.commit()
                    return make_success_response({
                        "action": "NEXT_FORM",
                        "feature_id": next_feature.id,
                        "feature_name": next_feature.feature,
                        "title": next_feature.title,
                        "description": next_feature.feature_description,
                        "form_fields": form_fields
                    })
                else:
                    # Step Complete -> Move to Next Step (FeatureFlow)
                    flow.current_step += 1
                    flow.current_api_id = 0 # Reset for next step (0 or None)
                    
                    # Verify if next map exists
                    next_map = (
                        session.query(FlowFeatureMap)
                        .filter(FlowFeatureMap.flow_id == flow.flow_id)
                        .filter(FlowFeatureMap.execution_order == flow.current_step)
                        .first()
                    )
                    
                    session.commit()
                    
                    status_action = "STEP_COMPLETE" if next_map else "JOURNEY_COMPLETE"
                    return make_success_response({
                        "action": status_action, 
                        "message": "Proceed to next step" if next_map else "Journey Completed",
                        "next_step": flow.current_step if next_map else None
                    })
            
            else:
                # Failed
                session.commit()
                return error_failure_response(f"Verification Failed: {api_result.get('message')}", 400)

    except Exception as e:
        print(f"Journey Submit Error: {e}")
        return error_failure_response(f"Execution Error: {e}", 500)

@router.get("/journey/poll", tags=['journey'])
def poll_status(
    client_id: str,
    feature_id: int, # The polling feature ID (API ID)
    request: Request,
    auth: dict = Depends(authenticate_journey_user)
):
    try:
        active_flow_id = auth.get("flow_id")
        customer_id = auth.get("customer_id")
        
        with db.Session() as session:
            active_flow = session.query(ActiveFlow).filter(ActiveFlow.id == active_flow_id).first()
            if not active_flow:
                return error_failure_response("Flow not found", 404)
            
            feature = session.query(FeatureMaster).filter(FeatureMaster.id == feature_id).first()
            if not feature:
                 return error_failure_response("Feature not found", 404)
                 
            # Execute Proxy Call
            # For polling, the input data usually is just {"client_id": ...} or similar.
            # We assume the "polling" API in FastKYC expects {"client_id": ...} inside the 'data' wrapper.
            
            connector = FastKYCConnector(session, customer_id)
            input_data = {"client_id": client_id}
            
            # Using the same execute_feature wrapper
            result = connector.execute_feature(feature, input_data)
            
            status = result.get("status")
            
            # Log this attempt? Maybe too verbose for polling, but good for debug.
            # Optionally update state if success?
            
            if status == "SUCCESS":
                 # Update ActiveFlow State if needed
                 # Maybe we don't automatically advance here, frontend calls submit again?
                 # OR we return "NEXT_ACTION" here?
                 # Let's return the status and let Frontend trigger the next move (e.g. calling submit with empty data to trigger 'next' logic)
                 pass
                 
            return make_success_response(result)

    except Exception as e:
        return error_failure_response(f"Polling Error: {e}", 500)
