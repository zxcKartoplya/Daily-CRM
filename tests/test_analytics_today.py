from datetime import date, datetime, timedelta

from app.models import Department, Job, Reviewer, User
from app.models.enums import DailyEntryStatus, DayType, UserRole, UserStatus
from tests.test_daily_entries import _seed_entry

TODAY = date.today()
TOMORROW = TODAY + timedelta(days=1)
LONG_AGO = datetime(2020, 1, 1)
OTHER_WEEKDAY = [(TODAY.isoweekday() % 7) + 1]


def _department(db, name="Разработка"):
    department = Department(name=name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def _job(db, department, name="Backend-разработчик"):
    reviewer = Reviewer(name=f"Ревьюер {name}", description="описание")
    db.add(reviewer)
    db.flush()
    job = Job(name=name, department_id=department.id, reviewer_id=reviewer.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _user(
    db,
    name,
    *,
    email=None,
    department=None,
    job=None,
    work_days=None,
    role=UserRole.EMPLOYEE.value,
    status=UserStatus.ACTIVE.value,
    created_at=LONG_AGO,
):
    user = User(
        name=name,
        email=email or f"{name.lower()}@test.com",
        role=role,
        status=status,
        department_id=department.id if department else None,
        job_id=job.id if job else None,
        schedule_type="weekly",
        work_days=work_days if work_days is not None else [1, 2, 3, 4, 5, 6, 7],
        created_at=created_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _today(client, headers, **params):
    response = client.get("/api/admin/analytics/today", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _by_name(body):
    return {row["user_name"]: row for row in body}


class TestAnalyticsToday:
    def test_empty_company_returns_empty_list(self, client, admin_headers):
        assert _today(client, admin_headers) == []

    def test_all_states(self, client, admin_headers, db):
        submitted = _user(db, "Submitted")
        drafted = _user(db, "Drafted")
        off = _user(db, "Off")
        _user(db, "Missing")
        _user(db, "Resting", work_days=OTHER_WEEKDAY)
        _seed_entry(db, submitted, TODAY)
        _seed_entry(db, drafted, TODAY, status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, off, TODAY, day_type=DayType.OFF.value)

        rows = _by_name(_today(client, admin_headers))
        assert {name: row["state"] for name, row in rows.items()} == {
            "Submitted": "submitted",
            "Drafted": "draft",
            "Off": "off",
            "Missing": "missing",
            "Resting": "rest",
        }

    def test_entry_out_of_schedule_wins_over_rest(self, client, admin_headers, db):
        employee = _user(db, "Overtime", work_days=OTHER_WEEKDAY)
        _seed_entry(db, employee, TODAY)

        [row] = _today(client, admin_headers)
        assert row["state"] == "submitted"

    def test_entry_fields(self, client, admin_headers, db):
        submitted = _user(db, "Submitted")
        drafted = _user(db, "Drafted")
        _user(db, "Missing")
        submitted_entry = _seed_entry(db, submitted, TODAY)
        submitted_entry.submitted_at = datetime.combine(TODAY, datetime.min.time()).replace(hour=10, minute=2)
        db.commit()
        draft_entry = _seed_entry(db, drafted, TODAY, status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, submitted, TODAY - timedelta(days=1))

        rows = _by_name(_today(client, admin_headers))
        assert rows["Submitted"]["entry_id"] == submitted_entry.id
        assert datetime.fromisoformat(rows["Submitted"]["submitted_at"]) == submitted_entry.submitted_at
        assert rows["Drafted"]["entry_id"] == draft_entry.id
        assert rows["Drafted"]["submitted_at"] is None
        assert rows["Missing"]["entry_id"] is None
        assert rows["Missing"]["submitted_at"] is None

    def test_department_and_job_fields(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        backend = _job(db, development)
        employee = _user(db, "Dev", department=development, job=backend)
        _user(db, "Nobody")

        rows = _by_name(_today(client, admin_headers))
        assert rows["Dev"] == {
            "user_id": employee.id,
            "user_name": "Dev",
            "department_id": development.id,
            "department_name": "Разработка",
            "job_name": "Backend-разработчик",
            "state": "missing",
            "entry_id": None,
            "submitted_at": None,
        }
        assert rows["Nobody"]["department_id"] is None
        assert rows["Nobody"]["department_name"] is None
        assert rows["Nobody"]["job_name"] is None

    def test_department_filter(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        support = _department(db, "Поддержка")
        _user(db, "Dev", department=development)
        _user(db, "Support", department=support)
        _user(db, "Nobody")

        body = _today(client, admin_headers, department_id=development.id)
        assert [row["user_name"] for row in body] == ["Dev"]
        assert len(_today(client, admin_headers)) == 3

    def test_department_without_employees_returns_empty_list(self, client, admin_headers, db):
        empty = _department(db, "Пустой")
        _user(db, "Nobody")

        assert _today(client, admin_headers, department_id=empty.id) == []

    def test_unknown_department_returns_404(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/today",
            headers=admin_headers,
            params={"department_id": 999},
        )
        assert response.status_code == 404

    def test_inactive_employees_and_admins_are_excluded(self, client, admin_headers, admin_user, db):
        _user(db, "Active")
        _user(db, "Fired", status=UserStatus.INACTIVE.value)
        _user(db, "Boss", role=UserRole.ADMIN.value)

        assert [row["user_name"] for row in _today(client, admin_headers)] == ["Active"]

    def test_employee_created_tomorrow_is_excluded(self, client, admin_headers, db):
        _user(db, "Today", created_at=datetime.combine(TODAY, datetime.min.time()))
        _user(db, "Tomorrow", created_at=datetime.combine(TOMORROW, datetime.min.time()))

        assert [row["user_name"] for row in _today(client, admin_headers)] == ["Today"]

    def test_sorted_by_name_then_id(self, client, admin_headers, db):
        second_ivanov = _user(db, "Иванов", email="ivanov1@test.com")
        first_ivanov = _user(db, "Иванов", email="ivanov2@test.com")
        _user(db, "Абрамов")
        _user(db, "Яковлев")

        body = _today(client, admin_headers)
        assert [row["user_name"] for row in body] == ["Абрамов", "Иванов", "Иванов", "Яковлев"]
        assert [row["user_id"] for row in body[1:3]] == sorted([second_ivanov.id, first_ivanov.id])

    def test_employee_cannot_read_today(self, client, employee_headers):
        assert client.get("/api/admin/analytics/today", headers=employee_headers).status_code == 403

    def test_unauthenticated_returns_401(self, client):
        assert client.get("/api/admin/analytics/today").status_code == 401
