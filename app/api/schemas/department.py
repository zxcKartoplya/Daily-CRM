from pydantic import BaseModel, ConfigDict


class DepartmentBase(BaseModel):
    name: str


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    name: str | None = None


class DepartmentInDBBase(DepartmentBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class Department(DepartmentInDBBase):
    employees_count: int
