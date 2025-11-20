from pydantic import BaseModel, EmailStr


class AdminBase(BaseModel):
    email: EmailStr
    full_name: str


class AdminCreate(AdminBase):
    password: str


class AdminUpdate(BaseModel):
    full_name: str | None = None
    password: str | None = None


class Admin(AdminBase):
    id: int

    class Config:
        from_attributes = True
