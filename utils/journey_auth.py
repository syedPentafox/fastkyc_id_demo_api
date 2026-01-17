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
