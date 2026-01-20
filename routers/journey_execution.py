import uuid
from traceback import print_tb
from fastapi import APIRouter, Depends, Body, HTTPException, Request
from sqlalchemy.orm import Session
from datetime import datetime
import json
import uuid

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
            
            if(flow.status == 'completed'):
                return error_failure_response("Flow is completed", 400)

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
            
                # Find index of current
                for i, api in enumerate(apis):
                    if api.api_id == flow.current_api_id:
                        target_api_dep = api
                        break
            
            if not target_api_dep:
                return error_failure_response("Configuration Error: No APIs in step", 500)
                
            # Load Feature Master
            feature = session.query(FeatureMaster).filter(FeatureMaster.id == target_api_dep.api_id).first()

            # 4. Dependency Injection & Data Preparation
            journey_state = flow.journey_state or {}
            final_data = input_data.copy()
            
            print(f"[DEPENDENCY INJECTION] journey_state: {journey_state}")
            print(f"[DEPENDENCY INJECTION] input_data: {input_data}")
            
            if "client_id" in journey_state and ("client_id" in feature.request and "client_id" not in final_data):
                final_data["client_id"] = journey_state["client_id"]
                print(f"[DEPENDENCY INJECTION] Injected client_id: {journey_state['client_id']}")

            # 5. Check for Missing Mandatory Fields (Should we show Form?) & Build Mapped Payload
            # Get Form Fields configuration
            field_mappings = (
                session.query(ApiRequiredField, FieldMaster)
                .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                .filter(ApiRequiredField.api_id == feature.id)
                .all()
            )
            
            form_fields = []
            missing_mandatory = []
            
            # Use 'final_data' which contains ClientID + UserInputs
            mapped_payload = {}
            # Preserve client_id if not mapped explicitly (usually it's standard)
            if "client_id" in final_data:
                mapped_payload["client_id"] = final_data["client_id"]

            for mapping, field in field_mappings:
                # Construct Form Config
                f_dict = {}
                for col in field.__table__.columns:
                        val = getattr(field, col.name)
                        if isinstance(val, datetime):
                            val = val.isoformat()
                        f_dict[col.name] = val
                f_dict['is_mandatory'] = mapping.is_mandatory
                form_fields.append(f_dict)
                
                # Check for Data Presence
                if field.field in final_data:
                    # Logic 1: Use key_name if present, else original field name
                    target_key = mapping.key_name if mapping.key_name else field.field
                    mapped_payload[target_key] = final_data[field.field]
                elif mapping.is_mandatory:
                     missing_mandatory.append(field.field)

            # Check if missing
            if missing_mandatory:
                # Update current_api_id so next request knows we are here
                if flow.current_api_id != feature.id:
                    flow.current_api_id = feature.id
                    session.commit()

                return make_success_response({
                    "action": "NEXT_FORM",
                    "feature_id": feature.id,
                    "feature_name": feature.feature,
                    "title": feature.title,
                    "description": feature.feature_description,
                    "form_fields": form_fields,
                    "validation_error": f"Missing fields: {missing_mandatory}" if input_data else None 
                })

            # 6. Execute via Connector (Only if all data is present)
            if feature.request and "redirect_url" in feature.request:
                 import os
                 redirect_url = os.getenv("JOURNEY_CALLBACK_URL")
                 if redirect_url:
                     mapped_payload["redirect_url"] = redirect_url
                     mapped_payload["state"] = str(uuid.uuid4())

            connector = FastKYCConnector(session, customer_id)
            api_result = connector.execute_feature(feature, mapped_payload)
            
            # 6. Handle Result
            status = api_result.get("status", "UNKNOWN")

            if not api_result.get("success"):
                raise Exception(api_result.get("message", "FastKYC validation failed"))

            data = api_result.get("data", {})

            client_id = None    
            if isinstance(data, dict):
                client_id = data.get("client_id")
            elif isinstance(data, list) and data:
                if isinstance(data[0], dict):
                    client_id = data[0].get("client_id")

            if client_id:
                journey_state["client_id"] = client_id
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
            if target_api_dep.api_type == "redirects" and (status == "SUCCESS" or status == "success"):
                # Redirect logic
                # The redirect API has been executed successfully
                # Now we need to advance to the NEXT API (which should be the polling/verification API)
                data = api_result.get("data")
                redirect_url = data.get("url")
                
                # Find the next API in sequence for polling
                current_idx = -1
                for i, api in enumerate(apis):
                    if api.api_id == target_api_dep.api_id:
                        current_idx = i
                        break
                
                # Check if there's a next API (should be the polling API)
                if current_idx + 1 < len(apis):
                    next_api = apis[current_idx + 1]
                    # Advance to next API (the polling API)
                    flow.current_api_id = next_api.api_id
                    session.commit()
                    
                    return make_success_response({
                        "action": "REDIRECT",
                        "data": data,
                        "url": redirect_url,
                        "poll_info": {
                            "api_id": next_api.api_id,  # Return NEXT API for polling, not current
                            "client_id": data.get("client_id")
                        }
                    })
                else:
                    # No next API? This shouldn't happen for redirect flows
                    session.commit()
                    return error_failure_response("Configuration Error: No polling API after redirect", 500)
                
            elif target_api_dep.api_type == "pooling":
                # Polling logic (if this API ITSELF is the one to poll, or if it triggers polling)
                # Usually 'pooling' type means "Keep calling me".
                # If status != SUCCESS, return WAIT.
                pass 
                
            # DEFAULT / SUCCESS behavior: Move to Next API
            if status == "SUCCESS" or status == "success" or "client_id" in api_result: # Loose success check
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
                        "form_fields": form_fields,
                        "data": api_result # Return the result of the JUST executed API
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

                    if status_action == "JOURNEY_COMPLETE":
                        flow.status = "completed"
                        flow.expires_at = datetime.now()
                        session.commit()

                    return make_success_response({
                        "action": status_action, 
                        "message": "Proceed to next step" if next_map else "Journey Completed",
                        "next_step": flow.current_step if next_map else None,
                        "data": api_result # Return the result of the JUST executed API
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
            
            # If polling succeeds, ensure client_id is in journey_state for subsequent APIs
            if status == "SUCCESS" or status == "success":
                # Extract client_id from result (could be in 'data' or top level)
                result_data = result.get("data", {})
                new_client_id = result_data.get("client_id") or result.get("client_id") or client_id
                
                # Always save client_id to journey_state (either from response or the one we used for polling)
                journey_state = active_flow.journey_state or {}
                journey_state["client_id"] = new_client_id
                active_flow.journey_state = journey_state
                session.commit()
                
                print(f"[POLLING SUCCESS] Saved client_id to journey_state: {new_client_id}")
                 
            return make_success_response(result)

    except Exception as e:
        return error_failure_response(f"Polling Error: {e}", 500)
