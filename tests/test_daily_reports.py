from datetime import date


TODAY = date.today().isoformat()
YESTERDAY = (date.today().replace(day=date.today().day - 1)).isoformat()


def _report_payload(report_date: str = TODAY) -> dict:
    return {
        "report_date": report_date,
        "yesterday_text": "Did some work",
        "today_text": "Will do more work",
        "blockers_text": None,
        "mood": "good",
        "self_rating": 8,
        "needs_help": False,
    }


class TestListDailyReports:
    def test_employee_can_list_own_reports(self, client, employee_headers, employee_user):
        response = client.get("/api/employee/daily-reports", headers=employee_headers)
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_unauthenticated_returns_401(self, client):
        response = client.get("/api/employee/daily-reports")
        assert response.status_code == 401

    def test_admin_cannot_use_employee_endpoint(self, client, admin_headers):
        response = client.get("/api/employee/daily-reports", headers=admin_headers)
        assert response.status_code == 403


class TestCreateDailyReport:
    def test_employee_creates_report(self, client, employee_headers, employee_user):
        response = client.post(
            "/api/employee/daily-reports",
            headers=employee_headers,
            json=_report_payload(),
        )
        assert response.status_code == 201
        data = response.json()
        assert data["report_date"] == TODAY
        assert data["user_id"] == employee_user.id
        assert data["today_text"] == "Will do more work"

    def test_duplicate_date_returns_400(self, client, employee_headers):
        client.post("/api/employee/daily-reports", headers=employee_headers, json=_report_payload())
        response = client.post(
            "/api/employee/daily-reports",
            headers=employee_headers,
            json=_report_payload(),
        )
        assert response.status_code == 400

    def test_two_different_dates_both_succeed(self, client, employee_headers):
        r1 = client.post("/api/employee/daily-reports", headers=employee_headers, json=_report_payload(TODAY))
        r2 = client.post("/api/employee/daily-reports", headers=employee_headers, json=_report_payload(YESTERDAY))
        assert r1.status_code == 201
        assert r2.status_code == 201

    def test_admin_cannot_create_employee_report(self, client, admin_headers):
        response = client.post(
            "/api/employee/daily-reports",
            headers=admin_headers,
            json=_report_payload(),
        )
        assert response.status_code == 403


class TestGetDailyReport:
    def test_get_own_report(self, client, employee_headers):
        created = client.post(
            "/api/employee/daily-reports",
            headers=employee_headers,
            json=_report_payload(),
        ).json()

        response = client.get(f"/api/employee/daily-reports/{created['id']}", headers=employee_headers)
        assert response.status_code == 200
        assert response.json()["id"] == created["id"]

    def test_get_nonexistent_report_returns_404(self, client, employee_headers):
        response = client.get("/api/employee/daily-reports/99999", headers=employee_headers)
        assert response.status_code == 404

    def test_employee_cannot_get_another_users_report(self, client, db, employee_headers):
        from app.models import User
        from app.models.enums import UserRole, UserStatus
        from app.core.security import hash_password, create_access_token
        from app.models import DailyReport
        from app.models.enums import DailyReportSource, DailyReportStatus
        from datetime import datetime

        other = User(
            name="Other Employee",
            email="other@test.com",
            password_hash=hash_password("pass"),
            role=UserRole.EMPLOYEE.value,
            status=UserStatus.ACTIVE.value,
        )
        db.add(other)
        db.commit()
        db.refresh(other)

        report = DailyReport(
            user_id=other.id,
            source=DailyReportSource.INTERNAL_WEB.value,
            status=DailyReportStatus.SUBMITTED.value,
            report_date=date.today(),
            submitted_at=datetime.utcnow(),
        )
        db.add(report)
        db.commit()
        db.refresh(report)

        response = client.get(f"/api/employee/daily-reports/{report.id}", headers=employee_headers)
        assert response.status_code == 404


class TestUpdateDailyReport:
    def test_update_own_report(self, client, employee_headers):
        created = client.post(
            "/api/employee/daily-reports",
            headers=employee_headers,
            json=_report_payload(),
        ).json()

        response = client.put(
            f"/api/employee/daily-reports/{created['id']}",
            headers=employee_headers,
            json={"today_text": "Changed text"},
        )
        assert response.status_code == 200
        assert response.json()["today_text"] == "Changed text"

    def test_update_date_to_existing_date_returns_400(self, client, employee_headers):
        client.post("/api/employee/daily-reports", headers=employee_headers, json=_report_payload(TODAY))
        r2 = client.post("/api/employee/daily-reports", headers=employee_headers, json=_report_payload(YESTERDAY))
        report2_id = r2.json()["id"]

        response = client.put(
            f"/api/employee/daily-reports/{report2_id}",
            headers=employee_headers,
            json={"report_date": TODAY},
        )
        assert response.status_code == 400


class TestDeleteDailyReport:
    def test_employee_deletes_own_report(self, client, employee_headers):
        created = client.post(
            "/api/employee/daily-reports",
            headers=employee_headers,
            json=_report_payload(),
        ).json()

        response = client.delete(f"/api/employee/daily-reports/{created['id']}", headers=employee_headers)
        assert response.status_code == 204

        get_response = client.get(f"/api/employee/daily-reports/{created['id']}", headers=employee_headers)
        assert get_response.status_code == 404

    def test_delete_nonexistent_returns_404(self, client, employee_headers):
        response = client.delete("/api/employee/daily-reports/99999", headers=employee_headers)
        assert response.status_code == 404
