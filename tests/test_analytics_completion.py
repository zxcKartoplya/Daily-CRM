from datetime import date, timedelta

from app.models import User
from app.models.enums import DailyEntryStatus, DayType, UserRole, UserStatus
from tests.test_analytics_timeseries import _department, _employee
from tests.test_daily_entries import _seed_entry
from tests.test_worker_statistics import _statistics

TODAY = date.today()


def _day(offset: int) -> date:
    return TODAY - timedelta(days=offset)


def _workers(client, headers, **params):
    response = client.get("/api/admin/analytics/workers", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _departments(client, headers, **params):
    response = client.get("/api/admin/analytics/departments", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _by_id(rows, key):
    return {row[key]: row for row in rows}


class TestWorkersCompletionAccess:
    def test_employee_cannot_read(self, client, employee_headers):
        assert client.get("/api/admin/analytics/workers", headers=employee_headers).status_code == 403

    def test_unauthenticated_returns_401(self, client):
        assert client.get("/api/admin/analytics/workers").status_code == 401


class TestWorkersCompletion:
    def test_only_employees_are_listed(self, client, admin_headers, admin_user, db):
        worker = _employee(db, "Worker")

        body = _workers(client, admin_headers)
        assert [row["user_id"] for row in body] == [worker.id]

    def test_no_employees_returns_empty_list(self, client, admin_headers):
        assert _workers(client, admin_headers) == []

    def test_matches_worker_statistics(self, client, admin_headers, db):
        rest_weekday = _day(2).isoweekday()
        fulltime = _employee(db, "Fulltime")
        parttime = _employee(db, "Parttime", work_days=[day for day in range(1, 8) if day != rest_weekday])
        for offset in (1, 3, 5, 8, 12, 20, 29):
            _seed_entry(db, fulltime, _day(offset))
        _seed_entry(db, fulltime, _day(4), status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, parttime, _day(6), day_type=DayType.OFF.value)
        _seed_entry(db, parttime, _day(2))
        _seed_entry(db, parttime, _day(9))

        for params in ({}, {"date_from": _day(10).isoformat(), "date_to": _day(1).isoformat()}):
            rows = _by_id(_workers(client, admin_headers, **params), "user_id")
            for worker in (fulltime, parttime):
                statistics = _statistics(client, admin_headers, worker.id, **params)
                row = rows[worker.id]
                assert row["working_days"] == statistics["working_days"]
                assert row["submitted"] == statistics["submitted_count"]
                assert row["completion_rate"] == statistics["completion_rate"]

    def test_employee_without_schedule(self, client, admin_headers, db):
        worker = _employee(db, "Unscheduled", schedule_type="none", work_days=None)
        _seed_entry(db, worker, _day(1))

        row = _workers(client, admin_headers)[0]
        assert row["working_days"] == 0
        assert row["submitted"] == 0
        assert row["completion_rate"] is None
        assert all(point["working_days"] == 0 for point in row["trend"])
        assert all(point["completion_rate"] is None for point in row["trend"])

    def test_off_counts_as_working_day_and_draft_is_not_submitted(self, client, admin_headers, db):
        worker = _employee(db, "Worker")
        _seed_entry(db, worker, _day(1))
        _seed_entry(db, worker, _day(2), status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, worker, _day(3), day_type=DayType.OFF.value)

        row = _workers(
            client,
            admin_headers,
            date_from=_day(3).isoformat(),
            date_to=_day(1).isoformat(),
        )[0]
        assert row["working_days"] == 3
        assert row["submitted"] == 1
        assert row["completion_rate"] == 0.3333

    def test_trend_is_split_into_weeks_from_the_end(self, client, admin_headers, db):
        worker = _employee(db, "Worker")
        _seed_entry(db, worker, _day(15))
        _seed_entry(db, worker, _day(0))

        row = _workers(
            client,
            admin_headers,
            date_from=_day(16).isoformat(),
            date_to=TODAY.isoformat(),
        )[0]
        assert [(point["date_from"], point["date_to"]) for point in row["trend"]] == [
            (_day(16).isoformat(), _day(14).isoformat()),
            (_day(13).isoformat(), _day(7).isoformat()),
            (_day(6).isoformat(), TODAY.isoformat()),
        ]
        assert [point["working_days"] for point in row["trend"]] == [3, 7, 7]
        assert [point["submitted"] for point in row["trend"]] == [1, 0, 1]
        assert [point["completion_rate"] for point in row["trend"]] == [0.3333, 0.0, 0.1429]
        assert sum(point["working_days"] for point in row["trend"]) == row["working_days"]
        assert sum(point["submitted"] for point in row["trend"]) == row["submitted"]

    def test_default_period_is_last_30_days(self, client, admin_headers, db):
        _employee(db, "Worker")

        trend = _workers(client, admin_headers)[0]["trend"]
        assert len(trend) == 5
        assert trend[0]["date_from"] == _day(29).isoformat()
        assert trend[0]["date_to"] == _day(28).isoformat()
        assert trend[-1]["date_to"] == TODAY.isoformat()
        assert sum(point["working_days"] for point in trend) == 30

    def test_single_day_period_has_one_point(self, client, admin_headers, db):
        _employee(db, "Worker")

        trend = _workers(
            client,
            admin_headers,
            date_from=TODAY.isoformat(),
            date_to=TODAY.isoformat(),
        )[0]["trend"]
        assert [(point["date_from"], point["date_to"]) for point in trend] == [
            (TODAY.isoformat(), TODAY.isoformat())
        ]

    def test_reversed_period_rejected(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/workers",
            headers=admin_headers,
            params={"date_from": TODAY.isoformat(), "date_to": _day(1).isoformat()},
        )
        assert response.status_code == 422

    def test_too_long_period_rejected(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/workers",
            headers=admin_headers,
            params={"date_from": _day(366).isoformat(), "date_to": TODAY.isoformat()},
        )
        assert response.status_code == 422


class TestDepartmentsCompletion:
    def test_department_sums_its_employees(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        support = _department(db, "Поддержка")
        first = _employee(db, "First", department=development)
        second = _employee(db, "Second", department=development, work_days=[_day(1).isoweekday()])
        stranger = _employee(db, "Stranger", department=support)
        _employee(db, "Nobody")
        _seed_entry(db, first, _day(1))
        _seed_entry(db, first, _day(2), status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, second, _day(1))
        _seed_entry(db, stranger, _day(1), day_type=DayType.OFF.value)

        params = {"date_from": _day(3).isoformat(), "date_to": _day(1).isoformat()}
        departments = _by_id(_departments(client, admin_headers, **params), "department_id")
        workers = _by_id(_workers(client, admin_headers, **params), "user_id")

        row = departments[development.id]
        assert row["employees_count"] == 2
        assert row["working_days"] == workers[first.id]["working_days"] + workers[second.id]["working_days"] == 4
        assert row["submitted"] == workers[first.id]["submitted"] + workers[second.id]["submitted"] == 2
        assert row["completion_rate"] == 0.5
        assert row["trend"] == [
            {
                "date_from": _day(3).isoformat(),
                "date_to": _day(1).isoformat(),
                "working_days": 4,
                "submitted": 2,
                "completion_rate": 0.5,
            }
        ]

        assert departments[support.id]["working_days"] == 3
        assert departments[support.id]["submitted"] == 0
        assert departments[support.id]["completion_rate"] == 0.0

    def test_inactive_employee_is_counted_like_department_dailies(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        employee = _employee(db, "Fired", department=development)
        employee.status = UserStatus.INACTIVE.value
        db.commit()

        row = _departments(
            client,
            admin_headers,
            date_from=_day(1).isoformat(),
            date_to=_day(1).isoformat(),
        )[0]
        assert row["employees_count"] == 1
        assert row["working_days"] == 1

    def test_admin_in_department_is_not_counted(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        db.add(
            User(
                name="Head",
                email="head@test.com",
                role=UserRole.ADMIN.value,
                status=UserStatus.ACTIVE.value,
                department_id=development.id,
                schedule_type="weekly",
                work_days=[1, 2, 3, 4, 5, 6, 7],
            )
        )
        db.commit()

        row = _departments(client, admin_headers)[0]
        assert row["working_days"] == 0
        assert row["completion_rate"] is None

    def test_department_without_employees(self, client, admin_headers, db):
        _department(db, "Пустой")

        row = _departments(client, admin_headers)[0]
        assert row["employees_count"] == 0
        assert row["entries_count"] == 0
        assert row["open_chains_count"] == 0
        assert row["blocked_items_count"] == 0
        assert row["working_days"] == 0
        assert row["submitted"] == 0
        assert row["completion_rate"] is None
        assert len(row["trend"]) == 5
        assert all(point["working_days"] == 0 for point in row["trend"])
        assert all(point["completion_rate"] is None for point in row["trend"])

    def test_default_period_is_last_30_days(self, client, admin_headers, db):
        development = _department(db, "Разработка")
        _employee(db, "Worker", department=development)

        row = _departments(client, admin_headers)[0]
        assert row["working_days"] == 30
        assert row["trend"][0]["date_from"] == _day(29).isoformat()
        assert row["trend"][-1]["date_to"] == TODAY.isoformat()

    def test_reversed_period_rejected(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/departments",
            headers=admin_headers,
            params={"date_from": TODAY.isoformat(), "date_to": _day(1).isoformat()},
        )
        assert response.status_code == 422

    def test_too_long_period_rejected(self, client, admin_headers):
        response = client.get(
            "/api/admin/analytics/departments",
            headers=admin_headers,
            params={"date_from": _day(366).isoformat(), "date_to": TODAY.isoformat()},
        )
        assert response.status_code == 422

    def test_employee_cannot_read(self, client, employee_headers):
        assert client.get("/api/admin/analytics/departments", headers=employee_headers).status_code == 403
