import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from utils.logger import get_logger
import jwt
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv
from utils.db_util import DatabaseHandler

logger = get_logger(__name__)
load_dotenv()

db = DatabaseHandler()

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
    expiration_time = datetime.now(timezone.utc) + timedelta(hours=float(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS")))
    payload.update({"exp": expiration_time})
    encoded_jwt = jwt.encode(payload, get_jwt_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict):
    payload = data.copy()
    expiration_time = datetime.now(timezone.utc) + timedelta(hours=float(os.getenv("REFRESH_TOKEN_EXPIRE_HOURS")))
    payload.update({"exp": expiration_time})
    encoded_jwt = jwt.encode(payload, get_jwt_secret_key(), algorithm=ALGORITHM)
    return encoded_jwt

async def validate_access_token(user_id,token):
    token_details= await db.get_data_from_table("customers",["id"],{"id_eq":user_id})
    print("user_id found -> ", token_details, _)
    if not token_details:
        raise credentials_exception

async def validate_user(user_id):
    """This function is used to validate user from the DB """
    user, _ = db.get_data_from_table("customers", ["id", "name"], {"id_eq": user_id})
    
    if not user:
        return False
    return True


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def verify_access_token(request : Request,token: str = Depends(oauth2_scheme)):
    """
    Decodes the incoming token and returns the key(user_id) present in the claims(dict)
    :param token: JWT string
    :return: user_id present in the jwt token
    """
    try:
        logger.info("Authentication Initiated.")
        payload = jwt.decode(token, get_jwt_secret_key(), algorithms=[ALGORITHM])
        # user_id: str = str(13)
        user_id: str = str(payload.get("sub"))
        # await validate_access_token(payload.get("sub"),token)
        if not user_id:
            raise credentials_exception
        
        is_user_valid = await validate_user(user_id)
        logger.info("userID=%s", user_id)
        if not is_user_valid:
            raise credentials_exception

        token_data = {"user_id":user_id}
        request.state.user_id = user_id
    except jwt.InvalidTokenError:
        raise credentials_exception
    logger.info("User has been authenticated.")
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
    print("token verified",user_id)
    return user_id