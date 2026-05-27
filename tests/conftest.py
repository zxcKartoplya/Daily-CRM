import os

os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["AUTH_SECRET"] = "test-secret-key-for-ci"

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.core.config import get_settings

get_settings.cache_clear()

from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models import User
from app.models.enums import UserRole, UserStatus
from app.core.security import create_access_token, hash_password

SQLALCHEMY_TEST_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


@pytest.fixture(autouse=True)
def clean_tables():
    yield
    db = TestingSessionLocal()
    try:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    finally:
        db.close()


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c


@pytest.fixture
def admin_user(db):
    user = User(
        name="Admin User",
        email="admin@test.com",
        password_hash=hash_password("adminpass"),
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def employee_user(db):
    user = User(
        name="Employee User",
        email="employee@test.com",
        password_hash=hash_password("emppass"),
        role=UserRole.EMPLOYEE.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(admin_user):
    return create_access_token(admin_user.id, admin_user.email, admin_user.role)


@pytest.fixture
def employee_token(employee_user):
    return create_access_token(employee_user.id, employee_user.email, employee_user.role)


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def employee_headers(employee_token):
    return {"Authorization": f"Bearer {employee_token}"}
