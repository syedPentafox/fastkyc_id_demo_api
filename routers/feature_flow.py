from fastapi import APIRouter, Depends, HTTPException, Request, Body
from typing import Optional
import logging
from orm_model.core_models import ApiRequiredField, FeatureApiDependency, FeatureFlow, FeatureMaster, FieldMaster, FlowFeatureMap, JourneyLog
from schemas.reqeust_schemas import FeatureFlowRequest
from utils.authentication import verify_access_token
from utils.custom_class import APIRouteWrapper
from utils.db_util import DatabaseHandler
from response_models.response_models import make_failure_response, make_success_response
from utils.error_handler import error_failure_response
from utils.feature_flow_helper import validate_feature_flow_apis
from utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(dependencies=[Depends(verify_access_token)])
db = DatabaseHandler()


@router.get("/feature_flow/feature", tags=["flow"])
def get_all_features_api_with_flow(
    status: Optional[str] = None,
    category: Optional[str] = None
):
    """
    Retrieves all available Features (APIs) and their mapped Form Fields.
    
    This is used by the frontend Form Builder to show available building blocks.
    Grouped by Feature ID.
    """
    with db.Session() as session:
        # Join FeatureMaster, ApiRequiredField, and FieldMaster
        query = (
            session.query(FeatureMaster, FieldMaster)
            .outerjoin(ApiRequiredField, ApiRequiredField.api_id == FeatureMaster.id)
            .outerjoin(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
        )
        
        # Apply filters
        if status:
            query = query.filter(FeatureMaster.status == status)
        if category:
            query = query.filter(FeatureMaster.category == category)
            
        results = query.all()
        print(results)
        if not results:
            return make_success_response(data=[], message="No features with field mappings found")

        # Group by Feature
        feature_map = {}
        
        for feature, field in results:
            if feature.id not in feature_map:
                feature_map[feature.id] = {
                    "id": feature.id,
                    "feature": feature.feature,
                    "title": feature.title,
                    "feature_description": feature.feature_description, 
                    "category": feature.category,
                    "icon": feature.icon,
                    "status": feature.status,
                    "url": feature.url,
                    # "request": feature.request,
                    # "response": feature.response,
                    "from_field": [],
                    "created_at": feature.created_date.isoformat() if feature.created_date and not isinstance(feature.created_date, str) else feature.created_date
                }

            # Serialize FieldMaster data
            if field:
                field_data = {c.name: getattr(field, c.name) for c in field.__table__.columns}
                # Handle datetimes
                if field_data.get('created_at'): field_data['created_at'] = field_data['created_at'].isoformat()
                if field_data.get('updated_at'): field_data['updated_at'] = field_data['updated_at'].isoformat()
            
                feature_map[feature.id]["from_field"].append(field_data)

        return make_success_response(list(feature_map.values()))


'''
this route is used to get a single feature by ID or Name
'''
@router.get("/feature_flow/feature/{identifier}", tags=["flow"])
def get_feature_by_id_or_name(identifier: str):
    with db.Session() as session:
        # Determine if identifier is ID or Name
        if identifier.isdigit():
            feature_results = (
                session.query(FeatureMaster, FieldMaster)
                .outerjoin(ApiRequiredField, ApiRequiredField.api_id == FeatureMaster.id)
                .outerjoin(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                .filter(FeatureMaster.id == int(identifier))
                .all()
            )
        else:
             feature_results = (
                session.query(FeatureMaster, FieldMaster)
                .outerjoin(ApiRequiredField, ApiRequiredField.api_id == FeatureMaster.id)
                .outerjoin(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                .filter(FeatureMaster.feature == identifier)
                .all()
            )

        if not feature_results:
             return make_success_response(data={}, message="Feature not found")

        # Process the single feature
        feature_obj = feature_results[0][0] # First row, FeatureMaster object
        feature_data = {
            "id": feature_obj.id,
            "feature": feature_obj.feature,
            "title": feature_obj.title,
            "feature_description": feature_obj.feature_description,
            "category": feature_obj.category,
            "icon": feature_obj.icon,
            "status": feature_obj.status,
            "url": feature_obj.url,
            "from_field": [],
            "created_at": feature_obj.created_date.isoformat() if feature_obj.created_date and not isinstance(feature_obj.created_date, str) else feature_obj.created_date
        }

        for _, field in feature_results:
            if field:
                field_data = {c.name: getattr(field, c.name) for c in field.__table__.columns}
                if field_data.get('created_at'): field_data['created_at'] = field_data['created_at'].isoformat() if not isinstance(field_data['created_at'], str) else field_data['created_at']
                if field_data.get('updated_at'): field_data['updated_at'] = field_data['updated_at'].isoformat() if not isinstance(field_data['updated_at'], str) else field_data['updated_at']
                feature_data["from_field"].append(field_data)
        
        return make_success_response(feature_data)


@router.get("/feature_flow",tags=["flow"])
def get_all_flow_features():
    """
    Retrieves all Feature Flows (Steps) and their constituent Features (APIs).
    
    A 'Feature Flow' is essentially a reusable 'Step' that contains one or more Features.
    Example: "Video KYC Step" (Feature Flow) -> contains "Digilocker", "Face Match" (Features/APIs).
    
    Structure:
    - Feature Flow
      - Features (Ordered by execution_order)
         - Form Fields
    """
    with db.Session() as session:
        # Query all feature flows with their API dependencies
        
        # 1 get all feature flows
        feature_flows = session.query(FeatureFlow).all()
        
        if not feature_flows:
            return make_success_response(data=[], message="No feature flows found")
        
        result = []
        
        for flow in feature_flows:
            flow_data = {
                "id": flow.id,
                "name": flow.name,
                "description": flow.description,
                "created_at": flow.created_at.isoformat() if flow.created_at and not isinstance(flow.created_at, str) else flow.created_at,
                "features": []
            }
            
            #2. Get all API dependencies for this feature flow
            api_deps = (
                session.query(FeatureApiDependency, FeatureMaster)
                .join(FeatureMaster, FeatureMaster.id == FeatureApiDependency.api_id)
                .filter(FeatureApiDependency.feature_id == flow.id)
                .order_by(FeatureApiDependency.execution_order)
                .all()
            )
            
            #3 Group APIs and their fields
            for dep, feature in api_deps:
                feature_data = {
                    "id": feature.id,
                    "feature": feature.feature,
                    "title": feature.title,
                    "feature_description": feature.feature_description,
                    "category": feature.category,
                    "icon": feature.icon,
                    "status": feature.status,
                    "url": feature.url,
                    # "request": feature.request,
                    # "response": feature.response,
                    "execution_order": dep.execution_order,
                    "api_type": dep.api_type,
                    "form_fields": []
                }
                
                # Get form fields for this API
                field_mappings = (
                    session.query(ApiRequiredField, FieldMaster)
                    .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                    .filter(ApiRequiredField.api_id == feature.id)
                    .all()
                )
                
                for mapping, field in field_mappings:
                    field_data = {c.name: getattr(field, c.name) for c in field.__table__.columns}
                    # Handle datetimes
                    if field_data.get('created_at'): 
                        field_data['created_at'] = field_data['created_at'].isoformat() if not isinstance(field_data['created_at'], str) else field_data['created_at']
                    if field_data.get('updated_at'): 
                        field_data['updated_at'] = field_data['updated_at'].isoformat() if not isinstance(field_data['updated_at'], str) else field_data['updated_at']
                    
                    field_data['is_mandatory'] = mapping.is_mandatory
                    feature_data["form_fields"].append(field_data)
                
                flow_data["features"].append(feature_data)
            
            result.append(flow_data)
        
        return make_success_response(result)


'''
this route is used to get a single feature flow by ID or Name, with optional filtering
'''
@router.get("/feature_flow/{identifier}", tags=["flow"])
def get_feature_flow_by_id_or_name(
    identifier: str
):
    with db.Session() as session:
        # Determine if identifier is ID or Name
        if identifier.isdigit():
            flow = session.query(FeatureFlow).filter(FeatureFlow.id == int(identifier)).first()
        else:
            flow = session.query(FeatureFlow).filter(FeatureFlow.name == identifier).first()

        if not flow:
            return make_success_response(data={}, message="Feature flow not found")

        flow_data = {
            "id": flow.id,
            "name": flow.name,
            "description": flow.description,
            "created_at": flow.created_at.isoformat() if flow.created_at and not isinstance(flow.created_at, str) else flow.created_at,
            "features": []
        }

        # Build the query for dependencies
        query = (
            session.query(FeatureApiDependency, FeatureMaster)
            .join(FeatureMaster, FeatureMaster.id == FeatureApiDependency.api_id)
            .filter(FeatureApiDependency.feature_id == flow.id)
        )

        # Order by execution order
        api_deps = query.order_by(FeatureApiDependency.execution_order).all()

        for dep, feature in api_deps:
            feature_data = {    
                "id": feature.id,
                "feature": feature.feature,
                "title": feature.title,
                "feature_description": feature.feature_description,
                "category": feature.category,
                "icon": feature.icon,
                "status": feature.status,
                "url": feature.url,
                "execution_order": dep.execution_order,
                "api_type": dep.api_type,
                "form_fields": []
            }

            # Get form fields for this API
            field_mappings = (
                session.query(ApiRequiredField, FieldMaster)
                .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
                .filter(ApiRequiredField.api_id == feature.id)
                .all()
            )

            for mapping, field in field_mappings:
                field_data = {c.name: getattr(field, c.name) for c in field.__table__.columns}
                if field_data.get('created_at'): 
                    field_data['created_at'] = field_data['created_at'].isoformat() if not isinstance(field_data['created_at'], str) else field_data['created_at']
                if field_data.get('updated_at'): 
                    field_data['updated_at'] = field_data['updated_at'].isoformat() if not isinstance(field_data['updated_at'], str) else field_data['updated_at']
                
                field_data['is_mandatory'] = mapping.is_mandatory
                feature_data["form_fields"].append(field_data)

            flow_data["features"].append(feature_data)

        return make_success_response(flow_data)


@router.post("/feature_flow", tags=['flow'])
async def create_feature_flow(payload: FeatureFlowRequest,):
    """
    Creates a new Feature Flow (Step) with ordered API dependencies.
    
    Payload Structure:
    - name: Unique name for this flow/step
    - description: Optional description
    - apis: List of APIs/Features to execute in this step, with configuration:
        - order: Execution sequence
        - api_type: polling, redirect, form, etc.
        - conditions: logic for when this API should run
    """

     # 1️⃣ Unique name
    existing, _ = db.get_data_from_table(
        "feature_flow",
        ["id"],
        {"name_eq": payload.name}
    )

    '''Checking if we dont have unique name'''
    if existing:
        return error_failure_response("The Feature Flow Name must be unique", 409)

    '''Check if the api has the object and validate the. order'''
    error = validate_feature_flow_apis(payload.apis, db)
    if error:
        return error
    
    '''If we reach here everything looks good. And good for execution'''
    try:
        with db.Session() as session:

            # Insert Feature Flow
            flow = FeatureFlow(
                name=payload.name,
                description=payload.desc
            )
            session.add(flow)
            session.flush()
            
            flow_id = flow.id

            # Insert API mappings
            for api in payload.apis:
                print("api data", api)
                dep = FeatureApiDependency(
                    feature_id=flow.id,
                    api_id=api.id,
                    execution_order=api.order,
                    api_type=api.api_type.value,
                    poll_interval=api.poll_interval,
                    poll_max_attempts=api.poll_max_attempts,
                    poll_success_path=api.poll_success_path,
                    poll_success_value=api.poll_success_value,
                    is_conditional=api.is_conditional,
                    condition_field=api.condition_field,
                    condition_value=api.condition_value
                )
                session.add(dep)

            session.commit()

    except Exception as e:
        session.rollback()
        return error_failure_response("Failed to create Feature Flow", 500)

    return make_success_response(
        data={"feature_id": flow_id},
        message=f"Feature Flow '{payload.name}' created successfully"
    )


@router.delete("/feature_flow/{identifier}", tags=["flow"])
def delete_feature_flow(
    identifier: str
):
    """
    Deletes a Feature Flow (Step) using a Smart Delete strategy.
    
    1. Soft Delete: If the Feature Flow has associated JourneyLogs (history), it is marked as 'deleted'.
       - Configuration (Dependencies, Mappings) is removed from the active table.
       - The main record remains for audit purposes.
       
    2. Hard Delete: If no JourneyLogs exist (unused), the record and all dependencies are physically deleted.
    """
    try:
        with db.Session() as session:
            # 1. Resolve ID
            if identifier.isdigit():
                flow = session.query(FeatureFlow).filter(FeatureFlow.id == int(identifier)).first()
            else:
                flow = session.query(FeatureFlow).filter(FeatureFlow.name == identifier).first()

            if not flow:
                return error_failure_response("Feature flow not found", 404)

            # 2. Validation: Check if used in any Flow (FlowFeatureMap)
            usage_count = session.query(FlowFeatureMap).filter(FlowFeatureMap.feature_id == flow.id).count()
            if usage_count > 0:
                return error_failure_response(
                    f"Cannot delete Feature Flow. It is currently used in {usage_count} Flows.",
                    400
                )

            # 3. Check for Journey Logs
            # If logs exist -> Soft Delete
            # If no logs -> Hard Delete
            
            log_usage = session.query(JourneyLog).filter(JourneyLog.feature_id == flow.id).count()
            
            try:
                if log_usage > 0:
                    # SOFT DELETE
                    
                    # 1. Detach from Flows (FlowFeatureMap)
                    session.query(FlowFeatureMap).filter(FlowFeatureMap.feature_id == flow.id).delete()
                    
                    # 2. Delete Dependencies (Configuration)
                    session.query(FeatureApiDependency).filter(FeatureApiDependency.feature_id == flow.id).delete()
                    
                    # 3. Mark as Deleted
                    flow.status = 'deleted'
                    session.commit()

                    return make_success_response(
                        data={"id": flow.id},
                        message=f"Feature Flow '{flow.name}' deleted (soft) successfully"
                    )
                else:
                    # HARD DELETE
                    
                    # 1. Detach from Flows
                    session.query(FlowFeatureMap).filter(FlowFeatureMap.feature_id == flow.id).delete()
                    
                    # 2. Delete Dependencies
                    session.query(FeatureApiDependency).filter(FeatureApiDependency.feature_id == flow.id).delete()
                    
                    # 3. Delete Feature Flow
                    session.delete(flow)
                    session.commit()

                    return make_success_response(
                        data={"id": flow.id},
                        message=f"Feature Flow '{flow.name}' deleted (hard) successfully"
                    )

            except Exception as e:
                session.rollback()
                raise e

    except Exception as e:
        print(f"Error deleting feature flow {identifier}: {e}")
        return error_failure_response(f"Failed to delete feature flow: {str(e)}", 500)


@router.patch("/feature_flow/{identifier}", tags=["flow"])
def update_feature_flow(
    identifier: str,
    payload: dict = Body(...)
):
    try:
        with db.Session() as session:
            # Resolve ID
            if identifier.isdigit():
                flow = session.query(FeatureFlow).filter(FeatureFlow.id == int(identifier)).first()
            else:
                flow = session.query(FeatureFlow).filter(FeatureFlow.name == identifier).first()

            if not flow:
                return error_failure_response("Feature flow not found", 404)

            if "name" in payload:
                flow.name = payload["name"]
            if "description" in payload:
                flow.description = payload["description"]
            
            # Commit updates
            session.commit()

            return make_success_response(
                data={"id": flow.id},
                message="Feature Flow updated successfully"
            )

    except Exception as e:
        print(f"Error updating feature flow {identifier}: {e}")
        return error_failure_response(f"Failed to update feature flow: {str(e)}", 500)
