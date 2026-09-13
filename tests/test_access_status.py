from datetime import datetime

import pytest

from app.core.security import create_access_token, hash_password
from app.models import Job, Reviewer, User
from app.models.enums import UserRole, UserStatus
from tests.test_analytics_today import _department, _today, _user

ENDPOINTS = ["/api/admin/workers", "/api/admin/users"]


def _login(client, email, password):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def _stored_user(db, *, status, last_login_at=None, password="secret", email="person@test.com"):
    user = User(
        name="Person",
        email=email,
        password_hash=hash_password(password) if password else None,
        role=UserRole.EMPLOYEE.value,
        status=status,
        last_login_at=last_login_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _update_url(endpoint, user):
    return f"{endpoint}/{user.id}"


class TestLoginAccess:
    def test_invited_user_logs_in_and_becomes_active(self, client, db):
        user = _stored_user(db, status=UserStatus.INVITED.value)

        response = _login(client, "person@test.com", "secret")

        assert response.status_code == 200, response.text
        assert response.json()["user"]["status"] == "active"
        db.refresh(user)
        assert user.status == UserStatus.ACTIVE.value
        assert user.last_login_at is not None

    def test_active_user_login_updates_last_login_at(self, client, db):
        user = _stored_user(db, status=UserStatus.ACTIVE.value, last_login_at=datetime(2020, 1, 1))

        assert _login(client, "person@test.com", "secret").status_code == 200

        db.refresh(user)
        assert user.status == UserStatus.ACTIVE.value
        assert user.last_login_at > datetime(2020, 1, 1)

    def test_inactive_user_is_rejected_and_not_touched(self, client, db):
        user = _stored_user(db, status=UserStatus.INACTIVE.value)

        response = _login(client, "person@test.com", "secret")

        assert response.status_code == 403
        db.refresh(user)
        assert user.status == UserStatus.INACTIVE.value
        assert user.last_login_at is None

    def test_invited_user_without_password_cannot_log_in(self, client, db):
        user = _stored_user(db, status=UserStatus.INVITED.value, password=None)

        assert _login(client, "person@test.com", "secret").status_code == 400
        db.refresh(user)
        assert user.status == UserStatus.INVITED.value

    def test_token_of_inactive_user_is_rejected(self, client, db):
        user = _stored_user(db, status=UserStatus.ACTIVE.value, last_login_at=datetime(2026, 1, 1))
        headers = {"Authorization": f"Bearer {create_access_token(user.id, user.email, user.role)}"}
        assert client.get("/api/auth/me", headers=headers).status_code == 200

        user.status = UserStatus.INACTIVE.value
        db.commit()

        assert client.get("/api/auth/me", headers=headers).status_code == 403

    def test_token_of_invited_user_is_accepted(self, client, db):
        user = _stored_user(db, status=UserStatus.INVITED.value)
        headers = {"Authorization": f"Bearer {create_access_token(user.id, user.email, user.role)}"}

        assert client.get("/api/auth/me", headers=headers).status_code == 200

    def test_created_worker_logs_in_after_invitation(self, client, admin_headers):
        created = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={"name": "Новичок", "email": "new@test.com", "password": "secret"},
        )
        assert created.json()["status"] == "invited"

        response = _login(client, "new@test.com", "secret")

        assert response.status_code == 200
        assert response.json()["user"]["status"] == "active"


@pytest.mark.parametrize("endpoint", ENDPOINTS)
class TestCreateAccessStatus:
    def test_without_status_user_is_invited(self, client, admin_headers, endpoint):
        response = client.post(
            endpoint,
            headers=admin_headers,
            json={"name": "Новичок", "email": "new@test.com", "password": "secret"},
        )
        assert response.status_code == 201, response.text
        assert response.json()["status"] == "invited"

    def test_active_status_still_means_invited(self, client, admin_headers, endpoint):
        response = client.post(
            endpoint,
            headers=admin_headers,
            json={"name": "Новичок", "email": "new@test.com", "password": "secret", "status": "active"},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "invited"

    def test_inactive_status_is_kept(self, client, admin_headers, endpoint):
        response = client.post(
            endpoint,
            headers=admin_headers,
            json={"name": "Новичок", "email": "new@test.com", "status": "inactive"},
        )
        assert response.status_code == 201
        assert response.json()["status"] == "inactive"

    def test_invited_status_is_rejected(self, client, admin_headers, endpoint):
        response = client.post(
            endpoint,
            headers=admin_headers,
            json={"name": "Новичок", "email": "new@test.com", "status": "invited"},
        )
        assert response.status_code == 422


@pytest.mark.parametrize("endpoint", ENDPOINTS)
class TestUpdateAccessStatus:
    def test_opening_access_for_never_logged_in_user_gives_invited(self, client, admin_headers, db, endpoint):
        user = _stored_user(db, status=UserStatus.INACTIVE.value)

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"status": "active"})

        assert response.status_code == 200, response.text
        assert response.json()["status"] == "invited"

    def test_opening_access_for_logged_in_user_gives_active(self, client, admin_headers, db, endpoint):
        user = _stored_user(db, status=UserStatus.INACTIVE.value, last_login_at=datetime(2026, 1, 1))

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"status": "active"})

        assert response.json()["status"] == "active"

    def test_opening_access_without_password_gives_invited(self, client, admin_headers, db, endpoint):
        user = _stored_user(
            db, status=UserStatus.INACTIVE.value, last_login_at=datetime(2026, 1, 1), password=None
        )

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"status": "active"})

        assert response.json()["status"] == "invited"

    @pytest.mark.parametrize("initial", [UserStatus.ACTIVE.value, UserStatus.INVITED.value])
    def test_closing_access_gives_inactive(self, client, admin_headers, db, endpoint, initial):
        user = _stored_user(db, status=initial, last_login_at=datetime(2026, 1, 1))

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"status": "inactive"})

        assert response.json()["status"] == "inactive"

    def test_invited_status_is_rejected(self, client, admin_headers, db, endpoint):
        user = _stored_user(db, status=UserStatus.ACTIVE.value, last_login_at=datetime(2026, 1, 1))

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"status": "invited"})

        assert response.status_code == 422
        db.refresh(user)
        assert user.status == UserStatus.ACTIVE.value

    def test_password_change_keeps_invited(self, client, admin_headers, db, endpoint):
        user = _stored_user(db, status=UserStatus.INVITED.value, password=None)

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"password": "newpass"})

        assert response.status_code == 200
        assert response.json()["status"] == "invited"

    def test_update_without_status_keeps_status(self, client, admin_headers, db, endpoint):
        user = _stored_user(db, status=UserStatus.INACTIVE.value)

        response = client.put(_update_url(endpoint, user), headers=admin_headers, json={"name": "Renamed"})

        assert response.json()["status"] == "inactive"


class TestTrackedEmployees:
    def test_invited_is_tracked_today_and_inactive_is_not(self, client, admin_headers, db):
        _user(db, "Working")
        _user(db, "Invited", status=UserStatus.INVITED.value)
        _user(db, "Closed", status=UserStatus.INACTIVE.value)

        names = {row["user_name"] for row in _today(client, admin_headers)}

        assert names == {"Working", "Invited"}

    def test_employees_covered_counts_invited(self, client, admin_headers, db):
        department = _department(db)
        reviewer = Reviewer(name="Ревьюер", description="описание")
        db.add(reviewer)
        db.flush()
        job = Job(name="Разработчик", department_id=department.id, reviewer_id=reviewer.id)
        db.add(job)
        db.commit()
        _user(db, "Working", job=job)
        _user(db, "Invited", job=job, status=UserStatus.INVITED.value)
        _user(db, "Closed", job=job, status=UserStatus.INACTIVE.value)

        body = client.get(f"/api/admin/reviewers/{reviewer.id}/usage", headers=admin_headers).json()

        assert body["employees_covered"] == 2
