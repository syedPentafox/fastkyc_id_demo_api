from fastapi import APIRouter, Depends, HTTPException, Request
import logging
from orm_model.core_models import ApiRequiredField, FeatureApiDependency, FeatureFlow, FeatureMaster, FieldMaster
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
def get_all_features_api_with_flow():
    with db.Session() as session:
        # Join FeatureMaster, ApiRequiredField, and FieldMaster
        results = (
            session.query(FeatureMaster, FieldMaster)
            .join(ApiRequiredField, ApiRequiredField.api_id == FeatureMaster.id)
            .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
            .filter(FeatureMaster.status == "active") 
            .all()
        )

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
                    "created_at": feature.created_date.isoformat() if feature.created_date else None
                }
            
            # Serialize FieldMaster data
    
            field_data = {c.name: getattr(field, c.name) for c in field.__table__.columns}
            # Handle datetimes
            if field_data.get('created_at'): field_data['created_at'] = field_data['created_at'].isoformat()
            if field_data.get('updated_at'): field_data['updated_at'] = field_data['updated_at'].isoformat()
            
            feature_map[feature.id]["from_field"].append(field_data)

        return make_success_response(list(feature_map.values()))

@router.get("/feature_flow",tags=["flow"])
def get_all_flow_features():
    with db.Session() as session:
        # Query all feature flows with their API dependencies
        
        # First, get all feature flows
        feature_flows = session.query(FeatureFlow).all()
        
        if not feature_flows:
            return make_success_response(data=[], message="No feature flows found")
        
        result = []
        
        for flow in feature_flows:
            flow_data = {
                "id": flow.id,
                "name": flow.name,
                "description": flow.description,
                "created_at": flow.created_at.isoformat() if flow.created_at else None,
                "features": []
            }
            
            # Get all API dependencies for this feature flow
            api_deps = (
                session.query(FeatureApiDependency, FeatureMaster)
                .join(FeatureMaster, FeatureMaster.id == FeatureApiDependency.api_id)
                .filter(FeatureApiDependency.feature_id == flow.id)
                .order_by(FeatureApiDependency.execution_order)
                .all()
            )
            
            # Group APIs and their fields
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
                        field_data['created_at'] = field_data['created_at'].isoformat()
                    if field_data.get('updated_at'): 
                        field_data['updated_at'] = field_data['updated_at'].isoformat()
                    
                    field_data['is_mandatory'] = mapping.is_mandatory
                    feature_data["form_fields"].append(field_data)
                
                flow_data["features"].append(feature_data)
            
            result.append(flow_data)
        
        return make_success_response(result)


@router.post("/feature_flow", tags=['flow'])
async def create_feature_flow(payload: FeatureFlowRequest,):

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