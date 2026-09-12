from datetime import date, timedelta
from uuid import uuid4

from app.models import Department, User
from app.models.enums import DayType, EntryItemStatus, UserRole, UserStatus
from tests.test_daily_entries import _seed_entry

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _employee(db, department, name, *, work_days=None, schedule_type="weekly"):
    user = User(
        name=name,
        email=f"{name.lower()}@test.com",
        role=UserRole.EMPLOYEE.value,
        status=UserStatus.ACTIVE.value,
        department_id=department.id,
        schedule_type=schedule_type,
        work_days=work_days if work_days is not None else [1, 2, 3, 4, 5, 6, 7],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _department(db):
    department = Department(name="Разработка")
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


class TestDepartmentDailies:
    def test_employee_without_entry_has_null_day(self, client, admin_headers, db):
        department = _department(db)
        _employee(db, department, "Silent")

        response = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": YESTERDAY.isoformat(), "date_to": YESTERDAY.isoformat()},
        )
        assert response.status_code == 200
        body = response.json()
        assert len(body["employees"]) == 1
        day = body["employees"][0]["days"][0]
        assert day["entry"] is None
        assert day["is_working_day"] is True

    def test_day_off_differs_from_missing_entry(self, client, admin_headers, db):
        department = _department(db)
        resting = _employee(db, department, "Resting")
        _employee(db, department, "Missing")
        _seed_entry(db, resting, YESTERDAY, day_type=DayType.OFF.value)

        body = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": YESTERDAY.isoformat(), "date_to": YESTERDAY.isoformat()},
        ).json()
        by_name = {employee["user_name"]: employee["days"][0] for employee in body["employees"]}
        assert by_name["Resting"]["entry"]["day_type"] == "off"
        assert by_name["Missing"]["entry"] is None

    def test_entry_items_are_included(self, client, admin_headers, db):
        department = _department(db)
        worker = _employee(db, department, "Worker")
        _seed_entry(
            db,
            worker,
            YESTERDAY,
            items=[(str(uuid4()), "ждём доступ", EntryItemStatus.BLOCKED.value)],
        )

        body = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": YESTERDAY.isoformat(), "date_to": YESTERDAY.isoformat()},
        ).json()
        items = body["employees"][0]["days"][0]["entry"]["items"]
        assert [item["status"] for item in items] == ["blocked"]

    def test_non_working_day_is_marked(self, client, admin_headers, db):
        department = _department(db)
        _employee(db, department, "Parttime", work_days=[TODAY.isoweekday()])

        body = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": TODAY.isoformat(), "date_to": TODAY.isoformat()},
        ).json()
        assert body["employees"][0]["days"][0]["is_working_day"] is True

        body = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": (TODAY + timedelta(days=1)).isoformat(), "date_to": (TODAY + timedelta(days=1)).isoformat()},
        ).json()
        assert body["employees"][0]["days"][0]["is_working_day"] is False

    def test_employee_cannot_read_department_dailies(self, client, employee_headers, db):
        department = _department(db)
        response = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=employee_headers,
        )
        assert response.status_code == 403

    def test_reversed_period_rejected(self, client, admin_headers, db):
        department = _department(db)
        response = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": TODAY.isoformat(), "date_to": YESTERDAY.isoformat()},
        )
        assert response.status_code == 400

    def test_unknown_department_returns_404(self, client, admin_headers):
        response = client.get("/api/admin/departments/999/dailies", headers=admin_headers)
        assert response.status_code == 404
