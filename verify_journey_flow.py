
import requests
import json
import time
import os
import uuid
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
import sys
sys.path.append(os.getcwd())

from utils.db_util import DatabaseHandler
from utils.journey_auth import create_journey_token
from orm_model.core_models import (
    Flow, ActiveFlow, FeatureFlow, FeatureMaster, 
    FlowFeatureMap, FeatureApiDependency, Customer, CustomerFlowMapping,
    FieldMaster, ApiRequiredField
)
from routers.journey_execution import resolve_journey_state

BASE_URL = "http://127.0.0.1:8001/api"

def setup_test_data(session):
    print("[Setup] Seeding Test Data...")
    
    # 1. Customer
    customer = session.query(Customer).filter(Customer.name == "manappuram_fin").first()
    if not customer:
        customer = Customer(
            name="TestAutomator",
            password="hashed_pw",
            role="admin",
            mobile="0000000000",
            email="test@auto.com"
        )
        session.add(customer)
        session.commit()
    
    user_id = customer.id

    # BYPASS: Insert API Key for TestAutomator (Unconditionally)
    try:
        from sqlalchemy import text
        session.execute(text("INSERT INTO api_key (customer_id, api_key, environment_type) VALUES (:cid, 'test_key_bypass', '1')"), {"cid": user_id})
        session.commit()
    except Exception as e:
        # Ignore if already exists, but ensure we commit/rollback
        session.rollback()
        # print(f"Key insert failed (likely exists): {e}")

    # 2. Features (Step 1: Collection)
    feature1 = session.query(FeatureMaster).filter(FeatureMaster.feature == "TestFeature1").first()
    if not feature1:
        feature1 = FeatureMaster(
            feature="TestFeature1",
            title="Personal Details",
            feature_description="Enter your details",
            status="active",
            url="/api/mock/provider" # Relative URL handled by fastkyc (mocked locally)
        )
        session.add(feature1)
        session.commit()
    
    # Always update URL for test
    feature1.url = "http://127.0.0.1:8001/api/mock/provider"
    session.commit()

    # Create fields only if needed (check if they exist roughly or just try/except)
    # Simple check:
    if not session.query(ApiRequiredField).filter(ApiRequiredField.api_id == feature1.id).first():
        pass # Only add fields if not bound
        # Fields
        f1 = FieldMaster(field="full_name", label="Full Name", type="text", interface="input")
        f2 = FieldMaster(field="age", label="Age", type="number", interface="input")
        session.add_all([f1, f2])
        session.commit()
        
        session.add(ApiRequiredField(api_id=feature1.id, field_id=f1.id, is_mandatory=True))
        session.add(ApiRequiredField(api_id=feature1.id, field_id=f2.id, is_mandatory=True))
        session.commit()

    # 3. Features (Step 2: Message/End)
    feature2 = session.query(FeatureMaster).filter(FeatureMaster.feature == "TestFeature2").first()
    if not feature2:
        feature2 = FeatureMaster(
            feature="TestFeature2",
            title="Completion",
            feature_description="Done",
            status="active"
        )
        session.add(feature2)
        session.commit()
    
    feature2.url = "http://127.0.0.1:8001/api/mock/provider"
    session.commit()

    # 4. Feature Flows (Wrappers)
    ff1 = session.query(FeatureFlow).filter(FeatureFlow.name == "TestStep1").first()
    if not ff1:
        ff1 = FeatureFlow(name="TestStep1", description="Step 1")
        session.add(ff1)
        session.commit()
        # Dep
        session.add(FeatureApiDependency(feature_id=ff1.id, api_id=feature1.id, execution_order=1))
        session.commit()

    ff2 = session.query(FeatureFlow).filter(FeatureFlow.name == "TestStep2").first()
    if not ff2:
        ff2 = FeatureFlow(name="TestStep2", description="Step 2")
        session.add(ff2)
        session.commit()
        # Dep
        session.add(FeatureApiDependency(feature_id=ff2.id, api_id=feature2.id, execution_order=1))
        session.commit()

    # 5. Flow
    flow = session.query(Flow).filter(Flow.name == "TestJourneyFlow").first()
    if not flow:
        flow = Flow(
            name="TestJourneyFlow",
            description="Auto Test Flow",
            created_by=user_id,
            status="active"
        )
        session.add(flow)
        session.commit()
        
        # Mappings
        session.add(FlowFeatureMap(flow_id=flow.id, feature_id=ff1.id, execution_order=1))
        session.add(FlowFeatureMap(flow_id=flow.id, feature_id=ff2.id, execution_order=2))
        session.add(CustomerFlowMapping(customer_id=user_id, flow_id=flow.id))
        session.commit()

    return flow, customer

def create_test_session():
    db = DatabaseHandler()
    with db.Session() as session:
        flow, customer = setup_test_data(session)
        
        # Create Active Flow
        active_flow_id = str(uuid.uuid4())
        active_flow = ActiveFlow(
            id=active_flow_id,
            flow_id=flow.id,
            end_customer_identifier={"name": "Tester", "phone": "111"},
            activated_by=customer.id,
            status='active',
            expires_at=datetime.now().replace(year=2030),
            current_step=1
        )
        session.add(active_flow)
        session.commit()
        
        token = create_journey_token({
            "flow_id": active_flow_id,
            "customer_id": customer.id,
            "end_customer": {"name": "Tester", "phone": "111"}
        })
        
        return active_flow_id, token

def run_verification():
    active_flow_id, token = create_test_session()
    headers = {"Authorization": f"Bearer {token}"}
    
    print(f"\n--- Starting Journey Test (Flow ID: {active_flow_id}) ---")
    
    # 1. Get Initial State (Expect Step 1 Form)
    res = requests.get(f"{BASE_URL}/journey/state", headers=headers)
    print(f"STATE 1 ({res.status_code}): {res.text[:200]}")
    if res.status_code != 200: return
    
    state = res.json()
    if state["ui"]["type"] != "FORM":
        print("FAIL: Expected FORM")
        return
        
    print(">> Step 1 (Form) Loaded OK.")
    
    # 2. Submit Form
    payload = {"full_name": "Antigravity", "age": 100}
    print(f"Submitting: {payload}")
    res = requests.post(f"{BASE_URL}/journey/next", json=payload, headers=headers)
    print(f"NEXT 1 ({res.status_code}): {res.text[:200]}")
    
    if res.status_code != 200: return
    state = res.json()
    
    # Expect Step 2 (Form/Message)
    # My setup made Step 2 a feature "TestFeature2". It has NO fields.
    # So `resolve_journey_state` will return FORM with empty fields.
    
    if state["ui"]["type"] == "FORM" and state["current_step"] == 2:
         print(">> Step 2 (Empty Form) Loaded OK.")
         
         # 3. Submit Step 2 (Empty)
         res = requests.post(f"{BASE_URL}/journey/next", json={}, headers=headers)
         print(f"NEXT 2 ({res.status_code}): {res.text[:200]}")
         
         # DEBUG: Check for step_response_data
         if "step_response_data" in state:
             print(f">> Step Response Data: {state.get('step_response_data')}")
         
         if res.status_code != 200: return
         state = res.json()
         
         # Expect Completed
         if state["status"] == "completed":
             print(">> SUCCESS: Flow Completed!")
         else:
             print(f"FAIL: Expected Completed, got {state['status']}")
             
    else:
        print(f"FAIL: Expected Step 2, got {state}")

if __name__ == "__main__":
    run_verification()
