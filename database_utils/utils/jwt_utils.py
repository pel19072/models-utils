# utils/jwt_utils.py
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from my_shared_db.schemas.user import UserOut
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

refresh_expire = int(os.getenv("REFRESH_TOKEN_EXPIRE"))
access_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE"))
secret_key = os.getenv("SECRET_KEY")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def create_token(
    data: dict, 
    expires_delta: Optional[timedelta] = None
):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    logger.info(f"secret key: {secret_key}")
    return jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)


def create_access_token(
    usuario: UserOut
):
    data = {"id": usuario.id, "role": usuario.role, "company_id": usuario.company_id}
    token = create_token(data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    logger.info(f"Access token created")
    return token
    
def create_refresh_token(usuario: UserOut):
    data = {"id": usuario.id}
    token = create_token(data, expires_delta=timedelta(days=access_expire))
    logger.info(f"Refresh token created")
    return token

def decode_token(token: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        logger.info(f"Payload: {payload}")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Signature has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Error: {e}")
    
