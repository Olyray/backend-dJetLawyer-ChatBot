from pydantic import BaseModel, EmailStr

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserLogin(UserBase):
    password: str

class UserInDB(UserBase):
    id: int
    is_active: bool
    google_id: str | None

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str