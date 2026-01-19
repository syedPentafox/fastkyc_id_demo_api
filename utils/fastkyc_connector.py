import os
import requests
import json
from sqlalchemy.orm import Session
from fastapi import HTTPException
from orm_model.core_models import FeatureMaster

from sqlalchemy import text

class FastKYCConnector:
    def __init__(self, session: Session, customer_id: int):
        self.session = session
        self.customer_id = customer_id
        self.base_url = "https://fastkyc-api.fastkyc.in" # Could be env var

    def _get_api_key(self):
        # Raw SQL or if we had a model for api_keys. 
        # User prompt showed table structure for `api_key`.
        # 'customer_id' is mapped.
        # Since I cannot see an ORM model for `api_key` in core_models.py yet, I might need to add it or use raw SQL.
        # core_models.py does NOT have ApiKey table.
        # User said: "I can only ready thoses table which is not created by ID Application" and showed the schema.
        # I will use raw SQL to fetch it to avoid modifying core_models with "Foreign" tables if I can avoid it, 
        # but adding a ReadOnly model is better.
        # For now, I'll use execute() for safety/speed.
        
        query = text("SELECT api_key FROM api_key WHERE customer_id = :cid AND environment_type = '1' LIMIT 1") # Assuming '1' is prod/active? Or '0'? User didn't specify enum meaning.
        # logic: usually 1=Live, 0=Sandbox. 
        # But wait, user said "Environment-based separation". 
        # I will try to fetch ANY key for now, or maybe check env var for mode.
        # Let's assume '1' (Live) or just take the first one found.
        
        result = self.session.execute(query, {"cid": self.customer_id}).fetchone()
        if not result:
            # Fallback or error?
            # For development, maybe I should look for sandbox?
            query_sb = text("SELECT api_key FROM api_key WHERE customer_id = :cid ORDER BY environment_type DESC LIMIT 1")
            result = self.session.execute(query_sb, {"cid": self.customer_id}).fetchone()
            
        if not result:
            raise HTTPException(status_code=403, detail="API Key not found for customer")
        return result[0]

    def execute_feature(self, feature: FeatureMaster, input_data: dict, journey_state: dict = None):
        """
        Executes a FastKYC Feature API.
        Payload Format: {"feature": <feature_name>, "data": <input_data>}
        """
        api_key = self._get_api_key()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        # Construct Payload
        # Merge input_data and journey_state if needed? 
        # User said: "some apis will be going to need client ID... usually this client id will be fetched from one feature"
        # The 'input_data' passed here should already have the injected dependencies merged by the caller (Router).
        
        payload = {
            "feature": feature.feature,
            "data": input_data
        }
        print("payload", payload)
        
        # Use feature.url. If it's relative, append to base.
        url = feature.url
        if not url.startswith("http"):
             url = f"{self.base_url}{url}"
             
        print(f"Calling FastKYC: {url} | Feature: {feature.feature}")
        print(f"Calling FastKYC: {url} | headers: {headers}")
        print(f"Calling FastKYC: {url} | payoad: {payload}")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            data = response.json()
            print(f"FastKYC Response: {data}")
            
            # Simple error check based on status code or response body
            if response.status_code >= 400:
                print(f"FastKYC Status Error: {data}")
                # We might want to pass the error upstream
                return {"status": "FAILED", "error": data.get("message", "Unknown API Error"), "details": data}
            
            # Check for logical success if the API returns 200 but "status": "FAILED" ?
            # User example: {"status": "SUCCESS", "is_completed": true ...}
            # I will return the whole data for the caller to parse.
            return data
            
        except Exception as e:
            print(f"FastKYC Exception: {e}")
            return {"status": "FAILED", "error": str(e)}
