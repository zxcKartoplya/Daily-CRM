from pydantic import BaseModel


class UserBase(BaseModel):
    name: str
    job_id: int


class UserCreate(UserBase):
    pass


class UserUpdate(UserBase):
    pass


class UserInDBBase(UserBase):
    id: int

    class Config:
        from_attributes = True


class User(UserInDBBase):
    pass
