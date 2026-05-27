from app.core.security import hash_password
from app.models import User
from app.models.enums import UserRole, UserStatus


class TestLogin:
    def test_login_success_returns_token_and_user(self, client, employee_user):
        response = client.post("/api/auth/login", json={
            "email": "employee@test.com",
            "password": "emppass",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["email"] == "employee@test.com"
        assert data["user"]["role"] == "employee"

    def test_login_wrong_password_returns_400(self, client, employee_user):
        response = client.post("/api/auth/login", json={
            "email": "employee@test.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 400

    def test_login_unknown_email_returns_400(self, client):
        response = client.post("/api/auth/login", json={
            "email": "nobody@test.com",
            "password": "whatever",
        })
        assert response.status_code == 400

    def test_login_inactive_user_returns_403(self, client, db):
        user = User(
            name="Inactive",
            email="inactive@test.com",
            password_hash=hash_password("pass"),
            role=UserRole.EMPLOYEE.value,
            status=UserStatus.INACTIVE.value,
        )
        db.add(user)
        db.commit()

        response = client.post("/api/auth/login", json={
            "email": "inactive@test.com",
            "password": "pass",
        })
        assert response.status_code == 403

    def test_login_admin_success(self, client, admin_user):
        response = client.post("/api/auth/login", json={
            "email": "admin@test.com",
            "password": "adminpass",
        })
        assert response.status_code == 200
        assert response.json()["user"]["role"] == "admin"


class TestMe:
    def test_me_with_valid_token(self, client, employee_headers, employee_user):
        response = client.get("/api/auth/me", headers=employee_headers)
        assert response.status_code == 200
        assert response.json()["email"] == "employee@test.com"

    def test_me_without_token_returns_401(self, client):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_with_invalid_token_returns_401(self, client):
        response = client.get("/api/auth/me", headers={"Authorization": "Bearer invalidtoken"})
        assert response.status_code == 401

    def test_me_returns_correct_role(self, client, admin_headers, admin_user):
        response = client.get("/api/auth/me", headers=admin_headers)
        assert response.status_code == 200
        assert response.json()["role"] == "admin"


class TestBootstrapAdmin:
    def test_bootstrap_creates_first_admin(self, client):
        response = client.post("/api/auth/bootstrap-admin", json={
            "name": "First Admin",
            "email": "firstadmin@test.com",
            "password": "securepass",
        })
        assert response.status_code == 201
        data = response.json()
        assert data["role"] == "admin"
        assert data["email"] == "firstadmin@test.com"

    def test_bootstrap_fails_when_admin_already_exists(self, client, admin_user):
        response = client.post("/api/auth/bootstrap-admin", json={
            "name": "Second Admin",
            "email": "second@test.com",
            "password": "pass",
        })
        assert response.status_code == 403

    def test_bootstrap_fails_duplicate_email(self, client, employee_user):
        response = client.post("/api/auth/bootstrap-admin", json={
            "name": "New Admin",
            "email": "employee@test.com",
            "password": "pass",
        })
        assert response.status_code == 400
