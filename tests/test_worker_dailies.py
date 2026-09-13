from datetime import date, datetime, timedelta
from uuid import uuid4

from app.models import Department, Job, Reviewer, User
from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus, OffReason, UserRole, UserStatus
from tests.test_daily_entries import _seed_entry

TODAY = date.today()


def _day(offset: int) -> date:
    return TODAY - timedelta(days=offset)


def _worker(db, name="Worker", *, work_days=None, schedule_type="weekly", department=None, job=None):
    user = User(
        name=name,
        email=f"{name.lower()}@test.com",
        role=UserRole.EMPLOYEE.value,
        status=UserStatus.ACTIVE.value,
        department_id=department.id if department else None,
        job_id=job.id if job else None,
        schedule_type=schedule_type,
        work_days=work_days if work_days is not None else [1, 2, 3, 4, 5, 6, 7],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _department_with_job(db):
    department = Department(name="Разработка")
    reviewer = Reviewer(name="Тимлид", description="Ревью разработки")
    db.add_all([department, reviewer])
    db.flush()
    job = Job(name="Backend-разработчик", department_id=department.id, reviewer_id=reviewer.id)
    db.add(job)
    db.commit()
    db.refresh(department)
    db.refresh(job)
    return department, job


def _dailies(client, headers, worker_id, **params):
    response = client.get(f"/api/admin/workers/{worker_id}/dailies", headers=headers, params=params)
    assert response.status_code == 200, response.text
    return response.json()


class TestWorkerDailiesAccess:
    def test_unknown_worker_returns_404(self, client, admin_headers):
        assert client.get("/api/admin/workers/999999/dailies", headers=admin_headers).status_code == 404

    def test_admin_is_not_a_worker(self, client, admin_headers, admin_user):
        response = client.get(f"/api/admin/workers/{admin_user.id}/dailies", headers=admin_headers)
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, client, employee_user):
        assert client.get(f"/api/admin/workers/{employee_user.id}/dailies").status_code == 401

    def test_employee_cannot_read_worker_dailies(self, client, employee_headers, employee_user):
        response = client.get(f"/api/admin/workers/{employee_user.id}/dailies", headers=employee_headers)
        assert response.status_code == 403


class TestWorkerDailiesPeriod:
    def test_default_period_is_last_30_days(self, client, admin_headers, db):
        worker = _worker(db)
        body = _dailies(client, admin_headers, worker.id)
        assert body["date_to"] == TODAY.isoformat()
        assert body["date_from"] == _day(29).isoformat()
        assert [day["date"] for day in body["days"]] == [_day(offset).isoformat() for offset in range(29, -1, -1)]
        assert all(day["entry"] is None for day in body["days"])

    def test_inverted_period_returns_422(self, client, admin_headers, db):
        worker = _worker(db)
        response = client.get(
            f"/api/admin/workers/{worker.id}/dailies",
            headers=admin_headers,
            params={"date_from": TODAY.isoformat(), "date_to": _day(1).isoformat()},
        )
        assert response.status_code == 422

    def test_too_long_period_returns_422(self, client, admin_headers, db):
        worker = _worker(db)
        response = client.get(
            f"/api/admin/workers/{worker.id}/dailies",
            headers=admin_headers,
            params={"date_from": _day(366).isoformat(), "date_to": TODAY.isoformat()},
        )
        assert response.status_code == 422


class TestWorkerDailiesDays:
    def test_all_days_in_order_including_empty(self, client, admin_headers, db):
        worker = _worker(db)
        _seed_entry(db, worker, _day(2))
        _seed_entry(db, _worker(db, "Other"), _day(3))

        body = _dailies(client, admin_headers, worker.id, date_from=_day(4).isoformat(), date_to=_day(0).isoformat())
        assert [day["date"] for day in body["days"]] == [_day(offset).isoformat() for offset in (4, 3, 2, 1, 0)]
        assert [day["entry"] is not None for day in body["days"]] == [False, False, True, False, False]
        assert body["days"][2]["entry"]["user_id"] == worker.id

    def test_entries_outside_period_are_excluded(self, client, admin_headers, db):
        worker = _worker(db)
        _seed_entry(db, worker, _day(5))
        _seed_entry(db, worker, TODAY + timedelta(days=1))

        body = _dailies(client, admin_headers, worker.id, date_from=_day(4).isoformat(), date_to=_day(0).isoformat())
        assert all(day["entry"] is None for day in body["days"])

    def test_is_working_day_follows_schedule(self, client, admin_headers, db):
        worker = _worker(db, work_days=[1, 2, 3, 4, 5])

        body = _dailies(client, admin_headers, worker.id, date_from=_day(6).isoformat(), date_to=_day(0).isoformat())
        assert body["schedule_type"] == "weekly"
        assert body["work_days"] == [1, 2, 3, 4, 5]
        assert [day["is_working_day"] for day in body["days"]] == [
            _day(offset).isoweekday() <= 5 for offset in range(6, -1, -1)
        ]

    def test_worker_without_schedule_has_no_working_days(self, client, admin_headers, db):
        worker = _worker(db, schedule_type="none", work_days=[])

        body = _dailies(client, admin_headers, worker.id, date_from=_day(6).isoformat(), date_to=_day(0).isoformat())
        assert body["schedule_type"] == "none"
        assert len(body["days"]) == 7
        assert not any(day["is_working_day"] for day in body["days"])

    def test_entry_carries_items_edited_at_and_off_reason(self, client, admin_headers, db):
        worker = _worker(db)
        chain_id = str(uuid4())
        edited = _seed_entry(
            db,
            worker,
            _day(2),
            items=[
                (chain_id, "ждём доступ", EntryItemStatus.BLOCKED.value),
                (str(uuid4()), "выкатили релиз", EntryItemStatus.DONE.value),
            ],
        )
        edited.edited_at = datetime(2026, 1, 5, 12, 30)
        day_off = _seed_entry(db, worker, _day(1), day_type=DayType.OFF.value, status=DailyEntryStatus.SUBMITTED.value)
        day_off.off_reason = OffReason.SICK_LEAVE.value
        db.commit()

        body = _dailies(client, admin_headers, worker.id, date_from=_day(2).isoformat(), date_to=_day(1).isoformat())
        work_entry, off_entry = (day["entry"] for day in body["days"])

        assert [item["status"] for item in work_entry["items"]] == ["blocked", "done"]
        assert work_entry["items"][0]["chain_id"] == chain_id
        assert work_entry["edited_at"].startswith("2026-01-05T12:30:00")
        assert work_entry["off_reason"] is None

        assert off_entry["day_type"] == "off"
        assert off_entry["off_reason"] == "sick_leave"
        assert off_entry["edited_at"] is None


class TestWorkerDailiesHeader:
    def test_worker_with_job_and_department(self, client, admin_headers, db):
        department, job = _department_with_job(db)
        worker = _worker(db, "Иванов Иван", department=department, job=job)

        body = _dailies(client, admin_headers, worker.id, date_from=_day(0).isoformat(), date_to=_day(0).isoformat())
        assert body["user_id"] == worker.id
        assert body["user_name"] == "Иванов Иван"
        assert body["job_name"] == "Backend-разработчик"
        assert body["department_name"] == "Разработка"

    def test_worker_without_job_and_department(self, client, admin_headers, db):
        worker = _worker(db)

        body = _dailies(client, admin_headers, worker.id, date_from=_day(0).isoformat(), date_to=_day(0).isoformat())
        assert body["job_name"] is None
        assert body["department_name"] is None
