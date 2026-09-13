from datetime import date, timedelta
from uuid import uuid4

from app.models import User
from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus, UserRole, UserStatus
from tests.test_daily_entries import _seed_entry

TODAY = date.today()


def _day(offset: int) -> date:
    return TODAY - timedelta(days=offset)


def _worker(db, name="Worker", *, work_days=None, schedule_type="weekly"):
    user = User(
        name=name,
        email=f"{name.lower()}@test.com",
        role=UserRole.EMPLOYEE.value,
        status=UserStatus.ACTIVE.value,
        schedule_type=schedule_type,
        work_days=work_days if work_days is not None else [1, 2, 3, 4, 5, 6, 7],
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _submitted(db, user, day, *, items=None):
    return _seed_entry(
        db,
        user,
        day,
        items=items if items is not None else [(str(uuid4()), "пункт", EntryItemStatus.IN_PROGRESS.value)],
    )


def _statistics(client, headers, worker_id, **params):
    response = client.get(
        f"/api/admin/workers/{worker_id}/statistics",
        headers=headers,
        params=params,
    )
    assert response.status_code == 200, response.text
    return response.json()


class TestWorkerStatisticsAccess:
    def test_unknown_worker_returns_404(self, client, admin_headers):
        assert client.get("/api/admin/workers/999999/statistics", headers=admin_headers).status_code == 404

    def test_admin_is_not_a_worker(self, client, admin_headers, admin_user):
        response = client.get(f"/api/admin/workers/{admin_user.id}/statistics", headers=admin_headers)
        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, client, employee_user):
        assert client.get(f"/api/admin/workers/{employee_user.id}/statistics").status_code == 401

    def test_employee_cannot_read_worker_statistics(self, client, employee_headers, employee_user):
        response = client.get(
            f"/api/admin/workers/{employee_user.id}/statistics",
            headers=employee_headers,
        )
        assert response.status_code == 403


class TestWorkerStatisticsPeriod:
    def test_default_period_is_last_30_days(self, client, admin_headers, db):
        worker = _worker(db)
        body = _statistics(client, admin_headers, worker.id)
        assert body["period_to"] == TODAY.isoformat()
        assert body["period_from"] == _day(29).isoformat()

    def test_empty_period_returns_zeros(self, client, admin_headers, db):
        worker = _worker(db, work_days=[])
        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(5).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["working_days"] == 0
        assert body["submitted_count"] == 0
        assert body["completion_rate"] is None
        assert body["avg_items_per_day"] == 0
        assert body["last_entry_at"] is None

    def test_inverted_period_returns_422(self, client, admin_headers, db):
        worker = _worker(db)
        response = client.get(
            f"/api/admin/workers/{worker.id}/statistics",
            headers=admin_headers,
            params={"date_from": _day(1).isoformat(), "date_to": _day(5).isoformat()},
        )
        assert response.status_code == 422

    def test_too_long_period_returns_422(self, client, admin_headers, db):
        worker = _worker(db)
        response = client.get(
            f"/api/admin/workers/{worker.id}/statistics",
            headers=admin_headers,
            params={"date_from": _day(400).isoformat(), "date_to": TODAY.isoformat()},
        )
        assert response.status_code == 422


class TestWorkerStatisticsCounters:
    def test_counters_sum_to_working_days(self, client, admin_headers, db):
        worker = _worker(db)
        _submitted(db, worker, _day(1))
        _submitted(db, worker, _day(2))
        _seed_entry(db, worker, _day(3), status=DailyEntryStatus.DRAFT.value)
        _seed_entry(db, worker, _day(4), day_type=DayType.OFF.value)

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(5).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["working_days"] == 5
        assert body["submitted_count"] == 2
        assert body["draft_count"] == 1
        assert body["off_count"] == 1
        assert body["missing_count"] == 1
        assert (
            body["submitted_count"] + body["draft_count"] + body["missing_count"] + body["off_count"]
            == body["working_days"]
        )
        assert body["completion_rate"] == 0.4

    def test_day_off_stays_inside_working_days(self, client, admin_headers, db):
        worker = _worker(db)
        _seed_entry(db, worker, _day(1), day_type=DayType.OFF.value)

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(1).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["working_days"] == 1
        assert body["off_count"] == 1
        assert body["completion_rate"] == 0.0

    def test_completion_rate_is_null_without_working_days(self, client, admin_headers, db):
        worker = _worker(db, schedule_type="none", work_days=None)
        _submitted(db, worker, _day(1))

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(3).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["working_days"] == 0
        assert body["completion_rate"] is None

    def test_items_and_chains(self, client, admin_headers, db):
        worker = _worker(db)
        open_chain, blocked_chain, dropped_chain = (str(uuid4()) for _ in range(3))
        _submitted(
            db,
            worker,
            _day(2),
            items=[
                (open_chain, "идёт", EntryItemStatus.IN_PROGRESS.value),
                (blocked_chain, "ждём доступ", EntryItemStatus.BLOCKED.value),
                (dropped_chain, "отменили", EntryItemStatus.DROPPED.value),
            ],
        )
        _submitted(
            db,
            worker,
            _day(1),
            items=[
                (open_chain, "готово", EntryItemStatus.DONE.value),
                (str(uuid4()), "ещё готово", EntryItemStatus.DONE.value),
                (str(uuid4()), "новая линия", EntryItemStatus.IN_PROGRESS.value),
            ],
        )

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(2).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["open_chains_count"] == 2
        assert body["blockers_count"] == 1
        assert body["dropped_chains_count"] == 1
        assert body["done_items_count"] == 2
        assert body["avg_items_per_day"] == 3.0
        assert body["last_entry_at"] is not None

    def test_period_limits_item_counters(self, client, admin_headers, db):
        worker = _worker(db)
        _submitted(
            db,
            worker,
            _day(10),
            items=[(str(uuid4()), "старый блокер", EntryItemStatus.BLOCKED.value)],
        )
        _submitted(
            db,
            worker,
            _day(1),
            items=[(str(uuid4()), "готово", EntryItemStatus.DONE.value)],
        )

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(2).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["blockers_count"] == 0
        assert body["done_items_count"] == 1
        assert body["open_chains_count"] == 1


class TestWorkerStatisticsStreak:
    def test_rest_day_does_not_break_streak(self, client, admin_headers, db):
        rest_weekday = _day(2).isoweekday()
        worker = _worker(db, work_days=[day for day in range(1, 8) if day != rest_weekday])
        _submitted(db, worker, _day(1))
        _submitted(db, worker, _day(3))

        body = _statistics(client, admin_headers, worker.id)
        assert body["streak"] == 2

    def test_day_off_does_not_break_streak(self, client, admin_headers, db):
        worker = _worker(db)
        _submitted(db, worker, _day(1))
        _seed_entry(db, worker, _day(2), day_type=DayType.OFF.value)
        _submitted(db, worker, _day(3))

        body = _statistics(client, admin_headers, worker.id)
        assert body["streak"] == 2

    def test_missing_day_breaks_streak(self, client, admin_headers, db):
        worker = _worker(db)
        _submitted(db, worker, _day(1))
        _submitted(db, worker, _day(3))

        body = _statistics(client, admin_headers, worker.id)
        assert body["streak"] == 1

    def test_draft_breaks_streak(self, client, admin_headers, db):
        worker = _worker(db)
        _submitted(db, worker, _day(1))
        _seed_entry(db, worker, _day(2), status=DailyEntryStatus.DRAFT.value)
        _submitted(db, worker, _day(3))

        body = _statistics(client, admin_headers, worker.id)
        assert body["streak"] == 1

    def test_streak_ignores_requested_period(self, client, admin_headers, db):
        worker = _worker(db)
        for offset in (1, 2, 3, 4):
            _submitted(db, worker, _day(offset))

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(1).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["streak"] == 4
        assert body["longest_streak"] == 1

    def test_longest_streak_is_limited_by_period(self, client, admin_headers, db):
        worker = _worker(db)
        for offset in (9, 8, 7):
            _submitted(db, worker, _day(offset))
        for offset in (5, 4, 3, 2):
            _submitted(db, worker, _day(offset))

        body = _statistics(
            client,
            admin_headers,
            worker.id,
            date_from=_day(9).isoformat(),
            date_to=_day(1).isoformat(),
        )
        assert body["longest_streak"] == 4
        assert body["streak"] == 0

    def test_no_entries_means_zero_streak(self, client, admin_headers, db):
        worker = _worker(db)
        body = _statistics(client, admin_headers, worker.id)
        assert body["streak"] == 0
        assert body["longest_streak"] == 0
