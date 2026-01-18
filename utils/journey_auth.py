import os
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status, Request
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"

def create_journey_token(data: dict):
    """
    Creates a JWT token for the end-user journey.
    Payload should include: flow_id, customer_id, end_customer details.
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=1) # Expiry 1 day
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_journey_token(token: str):
    """
    Verifies the journey token.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid journey token",
            headers={"WWW-Authenticate": "Bearer"},
        )

async def authenticate_journey_user(request: Request):
    """
    Dependency to authenticate journey user via Token.
    Supports 'Authorization: Bearer <token>' header or 'token' query parameter.
    """
    token = None
    
    # 1. Try Header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]
    
    # 2. Try Query Param (if header missing)
    if not token:
        token = request.query_params.get("token")
        
    if not token:
         raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
        
    payload = verify_journey_token(token)
    
    # Attach to request state
    request.state.journey_user = payload
    return payload
