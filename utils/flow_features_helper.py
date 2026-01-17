from sqlalchemy.orm import Session
from orm_model.core_models import (
    FeatureFlow, FeatureApiDependency, FeatureMaster, 
    ApiRequiredField, FieldMaster, Flow, FlowFeatureMap
)

def get_feature_flow_details(session: Session, feature_flow_id: int):
    """
    Fetches the full nested details of a single Feature Flow.
    Returns a dictionary representing the Feature Flow with its features and fields.
    """
    flow = session.query(FeatureFlow).filter(FeatureFlow.id == feature_flow_id).first()
    
    if not flow:
        return None

    flow_data = {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "created_at": flow.created_at.isoformat() if flow.created_at and not isinstance(flow.created_at, str) else flow.created_at,
        "features": []
    }

    # API Dependencies (Features in the Feature Flow)
    api_deps = (
        session.query(FeatureApiDependency, FeatureMaster)
        .join(FeatureMaster, FeatureMaster.id == FeatureApiDependency.api_id)
        .filter(FeatureApiDependency.feature_id == flow.id)
        .order_by(FeatureApiDependency.execution_order)
        .all()
    )

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

        # Form Fields for this Feature
        field_mappings = (
            session.query(ApiRequiredField, FieldMaster)
            .join(FieldMaster, FieldMaster.id == ApiRequiredField.field_id)
            .filter(ApiRequiredField.api_id == feature.id)
            .all()
        )

        for mapping, field in field_mappings:
            field_data = {c.name: getattr(field, c.name) for c in field.__table__.columns}
            
            # Handle datetimes safely
            if field_data.get('created_at'): 
                val = field_data['created_at']
                field_data['created_at'] = val.isoformat() if not isinstance(val, str) else val
            
            if field_data.get('updated_at'): 
                val = field_data['updated_at']
                field_data['updated_at'] = val.isoformat() if not isinstance(val, str) else val
            
            field_data['is_mandatory'] = mapping.is_mandatory
            feature_data["form_fields"].append(field_data)

        flow_data["features"].append(feature_data)

    return flow_data

def validate_flow_components(session: Session, flow_id: int):
    """
    Validates that the Flow and all its components (Feature Flows, Features) are active.
    Returns: (is_valid: bool, error_message: str)
    """
    # 1. Verify Flow
    flow = session.query(Flow).filter(Flow.id == flow_id).first()
    if not flow:
        return False, f"Flow ID {flow_id} not found."
    if flow.status != 'active':
        return False, f"Flow '{flow.name}' is not active."

    # 2. Verify Feature Flows
    mappings = (
        session.query(FlowFeatureMap, FeatureFlow)
        .join(FeatureFlow, FeatureFlow.id == FlowFeatureMap.feature_id)
        .filter(FlowFeatureMap.flow_id == flow_id)
        .all()
    )

    if not mappings:
        return False, f"Flow '{flow.name}' has no features mapped."

    for mapa, ff in mappings:
        if ff.status != 'active':
            return False, f"Feature Flow '{ff.name}' is inactive."

        # 3. Verify Features inside Feature Flow
        features = (
            session.query(FeatureApiDependency, FeatureMaster)
            .join(FeatureMaster, FeatureMaster.id == FeatureApiDependency.api_id)
            .filter(FeatureApiDependency.feature_id == ff.id)
            .all()
        )
        
        for dep, feat in features:
            if feat.status != 'active':
                return False, f"Feature '{feat.feature}' (in Flow '{ff.name}') is inactive."

    return True, "Valid"
