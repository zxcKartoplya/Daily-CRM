from contextlib import contextmanager
from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import event

from app.models import Department, Job, Reviewer, User
from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus, UserRole, UserStatus
from tests.conftest import engine
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


def _department(db, name="Разработка"):
    department = Department(name=name)
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


STATS_FIELDS = {
    "working_days": "working_days",
    "submitted": "submitted_count",
    "draft": "draft_count",
    "missing": "missing_count",
    "off": "off_count",
    "completion_rate": "completion_rate",
    "streak": "streak",
    "blockers": "blockers_count",
    "done_items": "done_items_count",
}


def _day(offset):
    return TODAY - timedelta(days=offset)


def _job(db, department, name="Backend-разработчик"):
    reviewer = Reviewer(name=f"Ревьюер {name}", description="описание")
    db.add(reviewer)
    db.flush()
    job = Job(name=name, department_id=department.id, reviewer_id=reviewer.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _assign_job(db, user, job):
    user.job_id = job.id
    db.commit()
    db.refresh(user)
    return user


def _department_dailies(client, headers, department_id, **params):
    response = client.get(
        f"/api/admin/departments/{department_id}/dailies",
        headers=headers,
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _worker_statistics(client, headers, worker_id, **params):
    response = client.get(
        f"/api/admin/workers/{worker_id}/statistics",
        headers=headers,
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


def _assert_stats_match(stats, statistics):
    assert set(stats) == set(STATS_FIELDS)
    assert {field: stats[field] for field in STATS_FIELDS} == {
        field: statistics[source] for field, source in STATS_FIELDS.items()
    }


@contextmanager
def _count_queries():
    statements = []

    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", before_cursor_execute)
    try:
        yield statements
    finally:
        event.remove(engine, "before_cursor_execute", before_cursor_execute)


class TestDepartmentDailiesJob:
    def test_job_is_included(self, client, admin_headers, db):
        department = _department(db)
        job = _job(db, department)
        _assign_job(db, _employee(db, department, "Hired"), job)
        _employee(db, department, "Unassigned")

        body = _department_dailies(client, admin_headers, department.id)
        by_name = {employee["user_name"]: employee for employee in body["employees"]}
        assert by_name["Hired"]["job_id"] == job.id
        assert by_name["Hired"]["job_name"] == "Backend-разработчик"
        assert by_name["Unassigned"]["job_id"] is None
        assert by_name["Unassigned"]["job_name"] is None


class TestDepartmentDailiesStats:
    def test_stats_match_worker_statistics(self, client, admin_headers, db):
        department = _department(db)
        busy = _employee(db, department, "Busy")
        other = _employee(db, department, "Other", work_days=[1, 3, 5])
        chain_a, chain_b, chain_c = str(uuid4()), str(uuid4()), str(uuid4())

        _seed_entry(
            db,
            busy,
            _day(12),
            items=[
                (chain_a, "интеграция", EntryItemStatus.IN_PROGRESS.value),
                (chain_b, "ждём доступ", EntryItemStatus.BLOCKED.value),
            ],
        )
        _seed_entry(
            db,
            busy,
            _day(8),
            items=[
                (chain_a, "интеграция", EntryItemStatus.BLOCKED.value),
                (str(uuid4()), "ревью", EntryItemStatus.DONE.value),
            ],
        )
        _seed_entry(
            db,
            busy,
            _day(6),
            status=DailyEntryStatus.DRAFT.value,
            items=[(str(uuid4()), "черновик", EntryItemStatus.DONE.value)],
        )
        _seed_entry(db, busy, _day(5), day_type=DayType.OFF.value)
        _seed_entry(
            db,
            busy,
            _day(3),
            items=[
                (chain_a, "интеграция", EntryItemStatus.DONE.value),
                (chain_b, "ждём доступ", EntryItemStatus.DROPPED.value),
            ],
        )
        _seed_entry(db, busy, _day(1), items=[(chain_c, "релиз", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, busy, TODAY, items=[(chain_c, "релиз", EntryItemStatus.BLOCKED.value)])
        _seed_entry(
            db,
            other,
            _day(4),
            items=[(str(uuid4()), "чужой блокер", EntryItemStatus.BLOCKED.value)],
        )

        params = {"date_from": _day(9).isoformat(), "date_to": _day(2).isoformat()}
        body = _department_dailies(client, admin_headers, department.id, **params)
        by_id = {employee["user_id"]: employee for employee in body["employees"]}

        busy_stats = by_id[busy.id]["stats"]
        assert busy_stats["blockers"] == 1
        assert busy_stats["done_items"] == 3
        assert busy_stats["draft"] == 1
        assert busy_stats["off"] == 1
        assert busy_stats["streak"] == 2
        assert busy_stats["completion_rate"] == 0.25

        for worker in (busy, other):
            _assert_stats_match(
                by_id[worker.id]["stats"],
                _worker_statistics(client, admin_headers, worker.id, **params),
            )

    def test_stats_cover_default_period(self, client, admin_headers, db):
        department = _department(db)
        worker = _employee(db, department, "Worker")
        _seed_entry(db, worker, _day(10), items=[(str(uuid4()), "старое", EntryItemStatus.DONE.value)])
        _seed_entry(db, worker, _day(2), items=[(str(uuid4()), "свежее", EntryItemStatus.BLOCKED.value)])

        body = _department_dailies(client, admin_headers, department.id)
        assert body["date_from"] == _day(6).isoformat()
        _assert_stats_match(
            body["employees"][0]["stats"],
            _worker_statistics(
                client,
                admin_headers,
                worker.id,
                date_from=body["date_from"],
                date_to=body["date_to"],
            ),
        )

    def test_stats_without_entries(self, client, admin_headers, db):
        department = _department(db)
        weekly = _employee(db, department, "Weekly")
        unscheduled = _employee(db, department, "Unscheduled", schedule_type="none")

        params = {"date_from": _day(6).isoformat(), "date_to": TODAY.isoformat()}
        body = _department_dailies(client, admin_headers, department.id, **params)
        by_id = {employee["user_id"]: employee for employee in body["employees"]}

        assert by_id[unscheduled.id]["stats"] == {
            "working_days": 0,
            "submitted": 0,
            "draft": 0,
            "missing": 0,
            "off": 0,
            "completion_rate": None,
            "streak": 0,
            "blockers": 0,
            "done_items": 0,
        }
        assert by_id[weekly.id]["stats"]["working_days"] == 7
        assert by_id[weekly.id]["stats"]["missing"] == 7
        assert by_id[weekly.id]["stats"]["completion_rate"] == 0.0

        for worker in (weekly, unscheduled):
            _assert_stats_match(
                by_id[worker.id]["stats"],
                _worker_statistics(client, admin_headers, worker.id, **params),
            )


class TestDepartmentDailiesQueries:
    def _populate(self, db, name, employees_count):
        department = _department(db, name)
        for index in range(employees_count):
            job = _job(db, department, f"Должность {name}{index}")
            employee = _assign_job(db, _employee(db, department, f"{name}{index}"), job)
            chain_id = str(uuid4())
            _seed_entry(db, employee, _day(3), items=[(chain_id, "задача", EntryItemStatus.IN_PROGRESS.value)])
            _seed_entry(
                db,
                employee,
                _day(1),
                items=[
                    (chain_id, "задача", EntryItemStatus.BLOCKED.value),
                    (str(uuid4()), "готово", EntryItemStatus.DONE.value),
                ],
            )
        return department

    def _measure(self, client, admin_headers, db, department):
        db.expire_all()
        with _count_queries() as statements:
            body = _department_dailies(client, admin_headers, department.id)
        return len(statements), body

    def test_query_count_does_not_grow_with_employees(self, client, admin_headers, db):
        single = self._populate(db, "Single", 1)
        many = self._populate(db, "Many", 5)

        single_count, single_body = self._measure(client, admin_headers, db, single)
        many_count, many_body = self._measure(client, admin_headers, db, many)

        assert len(single_body["employees"]) == 1
        assert len(many_body["employees"]) == 5
        assert all(employee["stats"]["blockers"] == 1 for employee in many_body["employees"])
        assert {employee["job_name"] for employee in many_body["employees"]} == {
            f"Должность Many{index}" for index in range(5)
        }
        assert single_count == many_count
