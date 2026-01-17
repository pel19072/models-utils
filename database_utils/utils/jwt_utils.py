# utils/jwt_utils.py
import jwt
import os
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException
from fastapi.security import OAuth2PasswordBearer
from database_utils.schemas.user import UserOut
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Load environment variables with defaults to avoid errors during import
refresh_expire = int(os.getenv("REFRESH_TOKEN_EXPIRE", "604800"))  # 7 days in seconds
access_expire = int(os.getenv("ACCESS_TOKEN_EXPIRE", "30"))  # 30 minutes
secret_key = os.getenv("SECRET_KEY", "default-secret-key-for-development")

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
    return jwt.encode(to_encode, secret_key, algorithm=ALGORITHM)


def create_access_token(usuario):
    """
    Create an access token for a user.

    Args:
        usuario: User object (can be UserOut, User model, or any object with id, roles, company_id)

    Returns:
        str: Encoded JWT token
    """
    # Get role names from the many-to-many relationship
    # Support both Pydantic models and SQLAlchemy models
    role_names = []
    if hasattr(usuario, 'roles'):
        roles = getattr(usuario, 'roles', [])
        if roles:
            # Handle SQLAlchemy relationship or Pydantic list
            role_names = [role.name if hasattr(role, 'name') else role for role in roles]

    data = {
        "id": usuario.id,
        "roles": role_names,
        "company_id": getattr(usuario, 'company_id', None),
        "is_super_admin": getattr(usuario, 'is_super_admin', False)
    }
    token = create_token(data, expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    logger.info(f"Access token created for user {usuario.id} with roles {role_names}")
    return token
    
def create_refresh_token(usuario: UserOut):
    data = {"id": usuario.id}
    token = create_token(data, expires_delta=timedelta(seconds=refresh_expire))
    logger.info(f"Refresh token created")
    return token

def decode_token(token: str):
    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        logger.info(f"{payload = }")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Signature has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Error: {e}")
    
