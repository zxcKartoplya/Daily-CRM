from pydantic import BaseModel


class DepartmentBase(BaseModel):
    name: str


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(DepartmentBase):
    pass


class DepartmentInDBBase(DepartmentBase):
    id: int
    admin_id: int

    class Config:
        from_attributes = True


class Department(DepartmentInDBBase):
    pass
