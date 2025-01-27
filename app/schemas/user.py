from pydantic import BaseModel, EmailStr
import uuid

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserInDB(UserBase):
    id: uuid.UUID
    is_active: bool
    google_id: str | None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class GoogleToken(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str
    user: UserCreate

class RefreshToken(BaseModel):
    refresh_token: str

class GoogleLoginRequest(BaseModel):
    token: str
