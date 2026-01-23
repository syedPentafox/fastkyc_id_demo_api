from fastapi import APIRouter, Depends, HTTPException, Request, Query, Body

from utils.authentication import verify_access_token
from utils.custom_class import APIRouteWrapper
from utils.db_util import DatabaseHandler
from response_models.response_models import make_success_response
from utils.error_handler import error_failure_response
from schemas.reqeust_schemas import FlowGenerationRequest, FlowActivationRequest
from orm_model.core_models import Flow, FeatureFlow, CustomerFlowMapping, FlowFeatureMap, ActiveFlow, JourneyLog
from typing import Optional
from utils.flow_features_helper import get_feature_flow_details, validate_flow_components
from utils.journey_auth import create_journey_token
from sqlalchemy import and_, func, cast, String
from datetime import datetime, timedelta
import os
import uuid
import json
from dotenv import load_dotenv

load_dotenv()

router = APIRouter(dependencies=[Depends(verify_access_token)])
db = DatabaseHandler()



@router.post("/flow/generate",tags=["flow"])
def initiate_id_flow(
    payload: FlowGenerationRequest,
    request: Request
):
    """
    Creates a new Flow configuration.
    
    1. Validates uniqueness of Flow Name for the user.
    2. Validates that all referenced Feature Flows (Steps) exist.
    3. Creates a new 'Flow' record.
    4. Maps the Flow to the Customer (CustomerFlowMapping).
    5. Maps the ordered Feature Flows to the Flow (FlowFeatureMap).
    """
    user_id = request.state.user_id

    # Unique name
    existing_flow, _ = db.get_data_from_table(
        "flows",
        ["id"],
        {"name_eq": payload.name, "created_by_eq": user_id}
    )

    if existing_flow:
        return error_failure_response(f"You already have a flow with this named '{payload.name}'", 409)

    # 2. Validate Feature Flows exist
    feature_ids = [item.id for item in payload.feature_flow]
    
    with db.Session() as session:
        # Check if all feature_ids exist in FeatureFlow table
        count = session.query(FeatureFlow).filter(FeatureFlow.id.in_(feature_ids)).count()
        
             # found missing IDs for better error message
        if count != len(set(feature_ids)):
             found_flows = session.query(FeatureFlow.id).filter(FeatureFlow.id.in_(feature_ids)).all()
             found_ids = {f.id for f in found_flows}
             missing_ids = set(feature_ids) - found_ids
             return error_failure_response(f"Feature Flows not found: {missing_ids}", 404)

        # Insertion  Arc
        try:
            # Insert Flow
            new_flow = Flow(
                name=payload.name,
                description=payload.desc,
                created_by=user_id,
                status="active" 
            )
            session.add(new_flow)
            session.flush() # to  Get ID
            
            flow_id = new_flow.id

            # Insert Customer Mapping
            mapping = CustomerFlowMapping(
                customer_id=user_id,
                flow_id=flow_id,
                is_enabled=True
            )
            session.add(mapping)

            # Insert Flow Feature Maps
            for item in payload.feature_flow:
                flow_map = FlowFeatureMap(
                    flow_id=flow_id,
                    feature_id=item.id,
                    execution_order=item.order
                )
                session.add(flow_map)
            
            session.commit()

            return make_success_response(
                data={"flow_id": flow_id},
                message=f"Flow '{payload.name}' created successfully"
            )

        except Exception as e:
            session.rollback()
            print(f"Error creating flow: {e}")
            return error_failure_response("Failed to create Flow", 500)


@router.get("/flow/features", tags=['flow'])
def get_all_features_flows(
    request: Request,
    search: Optional[str] = None
):
    try:
        user_id = request.state.user_id
        
        with db.Session() as session:
            # Query User's Flows
            query = (
                session.query(Flow)
                .join(CustomerFlowMapping, CustomerFlowMapping.flow_id == Flow.id)
                # .filter(CustomerFlowMapping.customer_id == user_id)
                .filter(Flow.status == 'active') 
            )

            # Search Filter
            if search:
                query = query.filter(Flow.name.ilike(f"%{search}%"))

            flows = query.all()

            # if not
            if not flows:
                return make_success_response(data=[], message="No flows found")

            results = []

            for flow in flows:
                flow_response = {
                    "id": flow.id,
                    "name": flow.name,
                    "description": flow.description,
                    "status": flow.status,
                    "created_at": flow.created_at.isoformat() if flow.created_at and not isinstance(flow.created_at, str) else flow.created_at,
                    "feature_flows": []
                }

                # Get Mapped Feature Flows for this Flow
                mappings = (
                    session.query(FlowFeatureMap)
                    .filter(FlowFeatureMap.flow_id == flow.id)
                    .order_by(FlowFeatureMap.execution_order)
                    .all()
                )

                for map_item in mappings:
                    # this will return The helper returns a structure with "features": [...].
                    ff_details = get_feature_flow_details(session, map_item.feature_id)
                    
                    if ff_details:
                        ff_details['order_in_flow'] = map_item.execution_order
                        flow_response["feature_flows"].append(ff_details)

                results.append(flow_response)

            return make_success_response(results)

    except Exception as e:
        print(f"Error fetching flows: {e}")
        return error_failure_response("Failed to fetch flows", 500)


@router.get("/flow/features/{id}", tags=['flow'])
def get_flow_by_id(
    id: int,
    request: Request
):
    try:
        user_id = request.state.user_id
        
        with db.Session() as session:
            # check ownership and existence
            flow = (
                session.query(Flow)
                .join(CustomerFlowMapping, CustomerFlowMapping.flow_id == Flow.id)
                .filter(CustomerFlowMapping.customer_id == user_id)
                .filter(Flow.id == id)
                .first()
            )

            if not flow:
                return error_failure_response("Flow not found", 404)

            flow_response = {
                "id": flow.id,
                "name": flow.name,
                "description": flow.description,
                "status": flow.status,
                "created_at": flow.created_at.isoformat() if flow.created_at and not isinstance(flow.created_at, str) else flow.created_at,
                "feature_flows": []
            }

            mappings = (
                session.query(FlowFeatureMap)
                .filter(FlowFeatureMap.flow_id == flow.id)
                .order_by(FlowFeatureMap.execution_order)
                .all()
            )

            for map_item in mappings:
                ff_details = get_feature_flow_details(session, map_item.feature_id)
                if ff_details:
                    ff_details['order_in_flow'] = map_item.execution_order
                    flow_response["feature_flows"].append(ff_details)

            return make_success_response(flow_response)

    except Exception as e:
        print(f"Error fetching flow {id}: {e}")
        return error_failure_response("Failed to fetch flow", 500)


@router.delete("/flow/{flow_id}", tags=['flow'])
def delete_flow(
    flow_id: int,
    request: Request
):
    try:
        user_id = request.state.user_id
        
        with db.Session() as session:
            # 1. Validate Flow Existence and Ownership
            flow = (
                session.query(Flow)
                # .join(CustomerFlowMapping, CustomerFlowMapping.flow_id == Flow.id)
                # .filter(CustomerFlowMapping.customer_id == user_id)
                .filter(Flow.id == flow_id)
                .first()
            )

            if not flow:
                return error_failure_response("Flow not found or access denied", 404)

            # 2. Check for Active Sessions (ActiveFlow)

            active_sessions = (
                session.query(ActiveFlow)
                .filter(ActiveFlow.flow_id == flow_id)
                .filter(ActiveFlow.status == 'active')
                .count()
            )

            if active_sessions > 0:
                return error_failure_response(
                    f"Cannot delete Flow. There are {active_sessions} active customer sessions using this flow.", 
                    400
                )

            # 3. Cleanup Expired Sessions (Zombies)

            now = datetime.now()
            expired_active_flows = (
                session.query(ActiveFlow)
                .filter(ActiveFlow.flow_id == flow_id)
                .filter(ActiveFlow.expires_at < now)
                .all()
            )

            for af in expired_active_flows:
                 # Check if this specific session has logs
                 has_logs = session.query(JourneyLog).filter(JourneyLog.active_flow_id == af.id).count() > 0
                 if not has_logs:
                      session.delete(af)
            
            session.flush()

            # 4. Check for Journey Logs (via ActiveFlow)
            # This is the "Smart Delete" Logic:
            # - If actual logs exist (meaning real usage history), we CANNOT delete the flow. 
            #   We SOFT DELETE it (status='deleted') to preserve audit history.
            # - If NO logs exist (e.g. only testing or unused), we HARD DELETE it to clean up the DB.
            
            # Check if any ActiveFlow associated with this Flow has JourneyLogs
            # Join ActiveFlow -> JourneyLog
            log_count = (
                session.query(JourneyLog)
                .join(ActiveFlow, ActiveFlow.id == JourneyLog.active_flow_id)
                .filter(ActiveFlow.flow_id == flow_id)
                .count()
            )

            try:
                if log_count > 0:
                    # CASE A: SOFT DELETE STRATEGY
                    # Usage exists, so we keep the Flow record but mark it deleted.
                    # We remove the configuration mappings (future instances) but keep history.
                    
                    # 1. Delete Configuration Mappings (Cleanup)
                    session.query(FlowFeatureMap).filter(FlowFeatureMap.flow_id == flow_id).delete()
                    session.query(CustomerFlowMapping).filter(CustomerFlowMapping.flow_id == flow_id).delete()
                    
                    # 2. Mark Flow as Deleted
                    flow.status = 'deleted'
                    
                    # 3. Terminate Active Sessions (Prevent further use)
                    session.query(ActiveFlow).filter(ActiveFlow.flow_id == flow_id).update({"status": "terminated"})

                    session.commit()
                    return make_success_response(data={"flow_id": flow_id}, message="Flow deleted successfully")

                else:
                    # CASE B: HARD DELETE STRATEGY
                    # No usage history, so it's safe to fully remove from DB.
                    
                    # 1. Delete Configuration
                    session.query(FlowFeatureMap).filter(FlowFeatureMap.flow_id == flow_id).delete()
                    session.query(CustomerFlowMapping).filter(CustomerFlowMapping.flow_id == flow_id).delete()
                    
                    # 2. Delete ActiveFlow (Safe because no logs exist, and we cleaned expired ones)
                    session.query(ActiveFlow).filter(ActiveFlow.flow_id == flow_id).delete()

                    # 3. Delete Flow
                    session.delete(flow)
                    
                    session.commit()

                    return make_success_response(
                        data={"flow_id": flow_id},
                        message="Flow deleted (hard) successfully"
                    )

            except Exception as e:
                session.rollback()
                print(f"Error deleting flow internal: {e}")
                raise e

    except Exception as e:
        print(f"Error deleting flow {flow_id}: {e}")
        return error_failure_response(f"Failed to delete flow: {str(e)}", 500)


@router.patch("/flow/{flow_id}", tags=['flow'])
def update_flow(
    flow_id: int,
    payload: dict = Body(...),
    request: Request = None
):
    try:
        user_id = request.state.user_id
        
        with db.Session() as session:
            flow = (
                session.query(Flow)
                .join(CustomerFlowMapping, CustomerFlowMapping.flow_id == Flow.id)
                .filter(CustomerFlowMapping.customer_id == user_id)
                .filter(Flow.id == flow_id)
                .first()
            )

            if not flow:
                return error_failure_response("Flow not found", 404)

            # Update fields
            if "name" in payload:
                flow.name = payload["name"]
            if "description" in payload:
                flow.description = payload["description"]
            if "status" in payload:
                flow.status = payload["status"]

            session.commit()

            return make_success_response(
                data={"id": flow.id}, 
                message="Flow updated successfully"
            )

    except Exception as e:
        print(f"Error updating flow {flow_id}: {e}")
        return error_failure_response(f"Failed to update flow: {str(e)}", 500)



@router.post("/flow/activate", tags=['flow'])
def activate_flow(
    payload: FlowActivationRequest,
    request: Request
):
    """
    activates a Flow for a specific End User, generating a unique Journey Session.
    
    1. Validates the Flow configuration (completeness check).
    2. Creates an 'ActiveFlow' record:
       - Stores end-user details (identifier).
       - Sets expiration time.
       - Generates a unique Active Flow ID (Session ID).
    3. Generates a secure JWT Journey Token containing the Session ID.
    4. Returns the Token and a precise Redirect URL for the frontend to launch the journey.
    """
    try:
        user_id = request.state.user_id # The CustomerID
        
        # 1. Validate Flow
        is_valid, msg = validate_flow_components(db.Session(), payload.flow_id)
        if not is_valid:
            return error_failure_response(msg, 400)

        with db.Session() as session:
            # 2. Deactivate Old Flows for this End User (SKIP complex match for now)
            # identifier_value = payload.end_customer_details.identifier
            
            now = datetime.now()
            
            # Update query using JSON match
            # session.query(ActiveFlow).filter(
            #     ActiveFlow.activated_by == user_id,
            #     ActiveFlow.status == 'active',
            # ).update(
            #     {
            #         "status": "inactive", 
            #         "expires_at": now 
            #     }, 
            #     synchronize_session=False
            # )
            
            # 3. Create New Active Flow
            expires_at = payload.expires if payload.expires else (now + timedelta(days=1))
            print(expires_at, "expires_at")
            # Serialize end_customer_details to dict then JSON
            customer_json = payload.end_customer_details.dict()
            
            new_active_flow = ActiveFlow(
                id=str(uuid.uuid4()),
                flow_id=payload.flow_id,
                end_customer_identifier=customer_json,
                activated_by=user_id,
                status='active',
                expires_at=expires_at,
                # current_step=1,
                # total_step=1 
            )
            
            session.add(new_active_flow)
            session.commit()
            session.refresh(new_active_flow)

            # 4. Generate Token
            token_payload = {
                "flow_id": new_active_flow.id,
                "customer_id": new_active_flow.activated_by,
                "end_customer": customer_json
            }
            token = create_journey_token(token_payload)
            
            # 5. Generate Redirect URL
            domain = os.getenv("REDIRECT_DOMAIN", "http://localhost:3000")
            print(domain)
            redirect_url = f"{domain}?tkn={token}"
            
            return make_success_response({
                "active_flow_id": new_active_flow.id,
                "created_at": new_active_flow.created_at.isoformat() if new_active_flow.created_at else None,
                "token": token,
                "redirect_url": redirect_url
            })

    except Exception as e:
        print(f"Error activating flow: {e}")
        return error_failure_response(f"Failed to activate flow. {e}", 500)
