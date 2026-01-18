import requests
import json
import uuid
import os
import jwt
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "http://127.0.0.1:8001/api"
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

def create_valid_token():
    payload = {
        "sub": "22", # Hardcoded user_id in backend is 22
        "exp": datetime.utcnow() + timedelta(hours=1)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def run_verification():
    print("🚀 Starting Verification...")
    
    token = create_valid_token()
    headers = {"Authorization": f"Bearer {token}"}
    
    # 2. Activate a Flow
    # We need a flow_id.
    # Let's list flows.
    print(f"\n1. Listing Flows with token: {token[:10]}...")
    res = requests.get(f"{BASE_URL}/flow/features", headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to list flows: {res.text}")
        return
        
    flows = res.json().get("data", [])
    if not flows:
        print("⚠️ No flows found. Please create a flow first via UI or Swagger.")
        return
        
    flow_id = flows[0]["id"]
    print(f"✅ Found Flow ID: {flow_id}")
    
    # 3. Activate Flow
    print(f"\n2. Activating Flow {flow_id}...")
    activate_payload = {
        "flow_id": flow_id,
        "end_customer_details": {
            "name": "Test User",
            "phone": "9999999999",
            "email": "test@example.com"
        },
        "auth_req": False
    }
    
    res = requests.post(f"{BASE_URL}/flow/activate", json=activate_payload, headers=headers)
    if res.status_code != 200:
        print(f"❌ Failed to activate flow: {res.text}")
        return
        
    data = res.json().get("data", {})
    journey_token = data.get("token")
    redirect_url = data.get("redirect_url")
    print(f"✅ Flow Activated!")
    print(f"   Token: {journey_token[:20]}...")
    print(f"   URL: {redirect_url}")
    
    # 4. Start Journey (Empty Submit to get first step)
    print("\n3. Starting Journey (Fetching First Step)...")
    journey_headers = {"Authorization": f"Bearer {journey_token}"}
    
    res = requests.post(f"{BASE_URL}/journey/submit", json={}, headers=journey_headers)
    if res.status_code != 200:
        print(f"❌ Failed to start journey: {res.text}")
        return
        
    step_data = res.json().get("data", {})
    print(f"✅ Received Step Data:")
    print(json.dumps(step_data, indent=2))
    
    if step_data.get("action") == "NEXT_FORM":
        feature_name = step_data.get("feature_name")
        print(f"\n4. Submitting Form for {feature_name}...")
        
        # Simulate submitting data
        # We assume generic inputs
        form_payload = {"full_name": "Test User", "mobile_number": "9999999999"}
        
        res = requests.post(f"{BASE_URL}/journey/submit", json=form_payload, headers=journey_headers)
        if res.status_code != 200:
            print(f"❌ Failed to submit step: {res.text}")
        else:
            print("✅ Step Submitted Successfully!")
            print(json.dumps(res.json(), indent=2))

if __name__ == "__main__":
    run_verification()
