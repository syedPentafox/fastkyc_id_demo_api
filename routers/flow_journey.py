from fastapi import APIRouter, Query, Body
from utils.db_util import DatabaseHandler
from response_models.response_models import make_success_response
from utils.error_handler import error_failure_response
from orm_model.core_models import (
    ActiveFlow, Flow, FlowFeatureMap, FeatureFlow, 
    FeatureApiDependency, FeatureMaster, ApiRequiredField, FieldMaster
)
from utils.journey_auth import create_journey_token
from sqlalchemy.orm import Session
from datetime import datetime
import json
import uuid

router = APIRouter()
db = DatabaseHandler()

def get_journey_flow_details(session: Session, flow_id: int):
    """
    Fetches the ordered list of Feature Flows (Steps) for a given Flow ID.
    Returns list of step objects.
    """
    # 1. Get ordered mappings
    mappings = (
        session.query(FlowFeatureMap, FeatureFlow)
        .join(FeatureFlow, FeatureFlow.id == FlowFeatureMap.feature_id)
        .filter(FlowFeatureMap.flow_id == flow_id)
        .order_by(FlowFeatureMap.execution_order)
        .all()
    )

    steps = []
    
    for mapa, ff in mappings:
        step_data = {
            "step_number": mapa.execution_order,
            "name": ff.name,
            "description": ff.description,
            "features": []
        }
        
        # 2. Get Features in this Feature Flow
        features_deps = (
            session.query(FeatureApiDependency, FeatureMaster)
            .join(FeatureMaster, FeatureMaster.id == FeatureApiDependency.api_id)
            .filter(FeatureApiDependency.feature_id == ff.id)
            .order_by(FeatureApiDependency.execution_order)
            .all()
        )
        
        for dep, feature in features_deps:
            feat_data = {
                "title": feature.title,
                "feature_description": feature.feature_description,
                "category": feature.category,
                "form_fields": []
            }
            
            # 3. Get Form Fields
            field_mappings = (
                session.query(ApiRequiredField, FieldMaster)
                .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                .filter(ApiRequiredField.api_id == feature.id)
                .all()
            )
            
            for mapping, field in field_mappings:
                f_dict = {}
                for col in field.__table__.columns:
                     val = getattr(field, col.name)
                     if isinstance(val, datetime):
                         val = val.isoformat()
                     f_dict[col.name] = val
                
                f_dict['is_mandatory'] = mapping.is_mandatory
                feat_data["form_fields"].append(f_dict)
            
            step_data["features"].append(feat_data)
        
        steps.append(step_data)
        
    return steps


@router.get("/flow/activate", tags=['journey'])
def start_flow_journey(
    flow_id: str = Query(..., description="Active Flow ID (UUID)")
):
    try:
        with db.Session() as session:
            # 1. Fetch Active Flow
            active_flow = session.query(ActiveFlow).filter(ActiveFlow.id == flow_id).first()
            
            if not active_flow:
                return error_failure_response("Invalid Flow ID", 404)
            
            if active_flow.status != 'active':
                return error_failure_response("Flow is not active", 400)
            
            if active_flow.expires_at and active_flow.expires_at < datetime.now():
                return error_failure_response("Flow has expired", 400)

            # 2. Fetch Flow Details (Name/Desc)
            flow_master = session.query(Flow).filter(Flow.id == active_flow.flow_id).first()
            if not flow_master:
                return error_failure_response("Flow configuration not found", 404)

            # 3. Build Steps Structure
            steps_structure = get_journey_flow_details(session, active_flow.flow_id)
            
            end_customer_data = active_flow.end_customer_identifier
            if isinstance(end_customer_data, str):
                try:
                    end_customer_data = json.loads(end_customer_data)
                except:
                    pass

            response_data = {
                "active_flow_id": active_flow.id,
                "flow_details": {
                    "name": flow_master.name,
                    "description": flow_master.description
                },
                "end_customer": end_customer_data,
                "auth_required": active_flow.authentication_required,
                "auth_type": active_flow.authentication_type,
                "status": active_flow.status,
                "expires_at": active_flow.expires_at.isoformat() if active_flow.expires_at else None,
                "steps": steps_structure
            }

            # 4. Generate Token if Auth NOT Required
            if not active_flow.authentication_required:
                token_payload = {
                    "flow_id": active_flow.id,
                    "customer_id": active_flow.activated_by,
                    "end_customer": end_customer_data
                }
                token = create_journey_token(token_payload)
                response_data["token"] = token
            
            return make_success_response(response_data)

    except Exception as e:
        print(f"Error in start_flow_journey: {e}")
        return error_failure_response(f"Internal Error: {e}", 500)



'''
For Demo we are simulatng this OTP routes but in future if we gonna added this auth service,
we just get to handle the api calling and some smallvalidation would be required and we are good.
'''
@router.post("/otp_init", tags=['journey'])
def initiate_otp(
    payload: dict = Body(...)
):
    try:
        phone = payload.get("phone")
        active_flow_id = payload.get("active_flow_id")
        
        if not phone or not active_flow_id:
             return error_failure_response("Phone and Active Flow ID required", 400)
        
        # Mock Response
        return make_success_response({
            "client_id": str(uuid.uuid4()),
            "otp_sent": True,
            "message": "OTP sent successfully"
        })
    except Exception as e:
        return error_failure_response(f"Error sending OTP: {e}", 500)


'''
Similarly we gonna handle this 
'''
@router.post("/submit_otp", tags=['journey'])
def submit_otp(
    payload: dict = Body(...)
):
    try:
        client_id = payload.get("client_id")
        otp = payload.get("otp")
        active_flow_id = payload.get("active_flow_id")
        
        if not client_id or not otp or not active_flow_id:
            return error_failure_response("Missing required fields", 400)

        # Mock Verification
        if otp != "123456":
             return error_failure_response("Invalid OTP", 400)
             
        # Generate Token
        with db.Session() as session:
            active_flow = session.query(ActiveFlow).filter(ActiveFlow.id == active_flow_id).first()
            if not active_flow:
                return error_failure_response("Invalid Active Flow ID", 400)
                
            end_customer_data = active_flow.end_customer_identifier
            if isinstance(end_customer_data, str):
                try:
                    end_customer_data = json.loads(end_customer_data)
                except:
                    pass
            
            token_payload = {
                "flow_id": active_flow.id,
                "customer_id": active_flow.activated_by,
                "end_customer": end_customer_data
            }
            token = create_journey_token(token_payload)
            
            return make_success_response({
                "token": token,
                "message": "Authentication successful"
            })
            
    except Exception as e:
        return error_failure_response(f"Error submitting OTP: {e}", 500)