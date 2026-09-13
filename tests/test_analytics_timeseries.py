from datetime import date, datetime, timedelta

from app.models import Department, User
from app.models.enums import DailyEntryStatus, DayType, UserRole, UserStatus
from tests.test_daily_entries import _seed_entry

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)
LONG_AGO = datetime(2020, 1, 1)


def _department(db, name="Разработка"):
    department = Department(name=name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def _employee(db, name, *, department=None, work_days=None, schedule_type="weekly", created_at=LONG_AGO):
    user = User(
        name=name,
        email=f"{name.lower()}@test.com",
        role=UserRole.EMPLOYEE.value,
        status=UserStatus.ACTIVE.value,
        department_id=department.id if department else None,
        schedule_type=schedule_type,
        work_days=work_days if work_days is not None else [1, 2, 3, 4, 5, 6, 7],
        created_at=created_at,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _timeseries(client, headers, **params):
    response = client.get("/api/admin/analytics/timeseries", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


class TestAnalyticsTimeseries:
    def test_day_without_data_is_zero_point(self, client, admin_headers, db):
        _employee(db, "Silent")

        body = _timeseries(
            client,
            admin_headers,
            date_from=YESTERDAY.isoformat(),
            date_to=YESTERDAY.isoformat(),
        )
        assert body == [
            {
                "date": YESTERDAY.isoformat(),
                "working_employees": 1,
                "submitted": 0,
                "draft": 0,
                "missing": 1,
                "off": 0,
                "completion_rate": 0.0,
            }
        ]

    def test_period_without_employees_returns_zero_points(self, client, admin_headers, db):
        body = _timeseries(
            client,
            admin_headers,
            date_from=YESTERDAY.isoformat(),
            date_to=TODAY.isoformat(),
        )
        assert [point["date"] for point in body] == [YESTERDAY.isoformat(), TODAY.isoformat()]
        assert all(point["working_employees"] == 0 for point in body)
        assert all(point["completion_rate"] is None for point in body)

    def test_states_are_counted(self, client, admin_headers, db):
        submitted = _employee(db, "Submitted")
        drafted = _employee(db, "Drafted")
        resting = _employee(db, "Resting")
        _employee(db, "Missing")
        _seed_entry(db, submitted, YESTERDAY)
        _seed_entry(db, drafted, YESTERDAY, status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, resting, YESTERDAY, day_type=DayType.OFF.value)

        point = _timeseries(
            client,
            admin_headers,
            date_from=YESTERDAY.isoformat(),
            date_to=YESTERDAY.isoformat(),
        )[0]
        assert point["working_employees"] == 4
        assert point["submitted"] == 1
        assert point["draft"] == 1
        assert point["off"] == 1
        assert point["missing"] == 1
        assert point["completion_rate"] == 0.25

    def test_day_out_of_schedule_is_not_counted(self, client, admin_headers, db):
        working = _employee(db, "Fulltime")
        _employee(db, "Parttime", work_days=[(TODAY.isoweekday() % 7) + 1])
        _seed_entry(db, working, TODAY)

        point = _timeseries(
            client,
            admin_headers,
            date_from=TODAY.isoformat(),
            date_to=TODAY.isoformat(),
        )[0]
        assert point["working_employees"] == 1
        assert point["submitted"] == 1
        assert point["missing"] == 0
        assert point["completion_rate"] == 1.0

    def test_completion_rate_is_null_without_working_employees(self, client, admin_headers, db):
        _employee(db, "Unscheduled", schedule_type="none", work_days=None)

        point = _timeseries(
            client,
            admin_headers,
            date_from=TODAY.isoformat(),
            date_to=TODAY.isoformat(),
        )[0]
        assert point["working_employees"] == 0
        assert point["completion_rate"] is None

    def test_employee_created_later_is_not_counted(self, client, admin_headers, db):
        _employee(db, "Newcomer", created_at=datetime.combine(TODAY, datetime.min.time()))

        body = _timeseries(
            client,
            admin_headers,
            date_from=YESTERDAY.isoformat(),
            date_to=TODAY.isoformat(),
        )
        assert body[0]["working_employees"] == 0
        assert body[0]["completion_rate"] is None
        assert body[1]["working_employees"] == 1

    def test_department_filter(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        support = _department(db, "Поддержка")
        developer = _employee(db, "Dev", department=development)
        _employee(db, "Support", department=support)
        _seed_entry(db, developer, YESTERDAY)

        point = _timeseries(
            client,
            admin_headers,
            date_from=YESTERDAY.isoformat(),
            date_to=YESTERDAY.isoformat(),
            department_id=development.id,
        )[0]
        assert point["working_employees"] == 1
        assert point["submitted"] == 1
        assert point["completion_rate"] == 1.0

        company = _timeseries(
            client,
            admin_headers,
            date_from=YESTERDAY.isoformat(),
            date_to=YESTERDAY.isoformat(),
        )[0]
        assert company["working_employees"] == 2
        assert company["completion_rate"] == 0.5

    def test_inactive_employee_is_not_counted(self, client, admin_headers, db):
        employee = _employee(db, "Fired")
        employee.status = UserStatus.INACTIVE.value
        db.commit()

        point = _timeseries(
            client,
            admin_headers,
            date_from=TODAY.isoformat(),
            date_to=TODAY.isoformat(),
        )[0]
        assert point["working_employees"] == 0

    def test_default_period_is_last_30_days(self, client, admin_headers, db):
        _employee(db, "Silent")

        body = _timeseries(client, admin_headers)
        assert len(body) == 30
        assert body[0]["date"] == (TODAY - timedelta(days=29)).isoformat()
        assert body[-1]["date"] == TODAY.isoformat()

    def test_reversed_period_rejected(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/timeseries",
            headers=admin_headers,
            params={"date_from": TODAY.isoformat(), "date_to": YESTERDAY.isoformat()},
        )
        assert response.status_code == 422

    def test_too_long_period_rejected(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/timeseries",
            headers=admin_headers,
            params={
                "date_from": (TODAY - timedelta(days=366)).isoformat(),
                "date_to": TODAY.isoformat(),
            },
        )
        assert response.status_code == 422

    def test_unknown_department_returns_404(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/timeseries",
            headers=admin_headers,
            params={"department_id": 999},
        )
        assert response.status_code == 404

    def test_employee_cannot_read_timeseries(self, client, employee_headers):
        assert client.get("/api/admin/analytics/timeseries", headers=employee_headers).status_code == 403

    def test_unauthenticated_returns_401(self, client):
        assert client.get("/api/admin/analytics/timeseries").status_code == 401
