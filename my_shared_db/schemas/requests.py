from pydantic import BaseModel, EmailStr, Field

from schemas.company import CompanyCreate
from schemas.user import UserCreate

# --- Login ---
class LoginRequest(BaseModel):
    usuario_id: EmailStr
    password: str

# --- Company Signup ---
class SignupUserRequest(UserCreate):
    pass

class SignupCompanyRequest(BaseModel):
    company: CompanyCreate
    user: UserCreate

class RefreshTokenRequest(BaseModel):
    refresh_token: str = Field(..., description="A valid refresh token previously issued")
    
    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }