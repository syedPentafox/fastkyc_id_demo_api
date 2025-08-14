import logging
import os
from datetime import datetime, timedelta, timezone
from passlib.context import CryptContext
import jwt
from dotenv import load_dotenv
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer

from utils.db_connection import db

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
load_dotenv()

"""
SECRET_KEY - The key to use for signing the claim set. Can be individual JWK or JWK set
HS256 - The algorithm to use for signing the the claims.  Defaults to HS256.
"""
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
forbidden_exception = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="You are forbidden to use this resource",
    headers={"WWW-Authenticate": "Bearer"},
)


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password, hashed_password):
    """
    Compare the password provided by the user and hashed password stored in db and verifies its authenticity
    :param plain_password: un-hashed password provided by the user while logging in
    :param hashed_password: hashed password that was stored during user signup
    :return: True in case of match; False when unmatched
    """
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password):
    """
    hash a password coming from the user
    :param password: Provided by the user
    :return: Hashed password
    """
    return pwd_context.hash(password)


def get_jwt_secret_key():
    """Fetches the secret key from redis and if the connection fails it defaults to the key present in env variable"""
    return SECRET_KEY


def create_access_token(data):
    """
    Creates a JWT access token with an expiration time(defined in the env file)
    :param data: A dict object is a claim set to sign
    :return: A JWT string
    """
    payload = data.copy()
    expiration_time = datetime.now(timezone.utc) + timedelta(
        hours=float(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS"))
    )
    payload.update({"exp": expiration_time})
    encoded_jwt = jwt.encode(payload, get_jwt_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict):
    payload = data.copy()
    expiration_time = datetime.now(timezone.utc) + timedelta(
        hours=float(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS"))
    )
    payload.update({"exp": expiration_time})
    encoded_jwt = jwt.encode(payload, get_jwt_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt


def validate_access_token(user_id, token):
    token_details, _ = db.get_data_from_table(
        "user_session_tokens", ["id"], {"token_eq": token}
    )
    if not token_details:
        raise credentials_exception


# Assuming you have OAuth2PasswordBearer set up
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def verify_access_token(token: str = Depends(oauth2_scheme)):
    print(">>>>>token<<<<<<")
    """
    Decodes the incoming token and returns the key(user_id) present in the claims(dict)
    :param token: JWT string
    :return: user_id present in the jwt token
    """
    try:
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=[ALGORITHM])
        user_id: str = str(payload.get("user_id"))
        # validate_access_token(payload.get("user_id"),token)
        if not user_id:
            raise credentials_exception
        token_data = {"user_id": user_id}
    except jwt.InvalidTokenError:
        raise credentials_exception
    return token_data.get("user_id")


async def get_user_id_from_token(request):
    """
    Decode the jwt token and returns the dict key user_id
    :param request: Request object that contains the bearer token
    :return: user_id encoded in the jwt token
    """
    token = await OAuth2PasswordBearer(tokenUrl="login")(request)
    print("Token verify")
    user_id = verify_access_token(token)
    print("token verified", user_id)
    return user_id


async def get_user_id_from_refresh_token(token):
    try:
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=[ALGORITHM])
        user_id: str = str(payload.get("user_id"))
        if not user_id:
            raise credentials_exception
        token_data = {"user_id": user_id}
    except jwt.InvalidTokenError:
        raise credentials_exception
    return token_data.get("user_id")

def create_access_token_ncrp(data: dict, expires_delta: int = 60):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")

def create_refresh_token_ncrp(data: dict, expires_delta: int = 1440):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, os.getenv("JWT_SECRET_KEY"), algorithm="HS256")