from datetime import date, timedelta
from uuid import uuid4

from app.models.enums import DayType, EntryItemStatus
from tests.test_daily_entries import _all_week, _seed_entry

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


class TestEmployeeStatistics:
    def test_empty_statistics(self, client, employee_headers, employee_user):
        response = client.get("/api/employee/statistics", headers=employee_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["streak"] == 0
        assert body["open_chains_count"] == 0
        assert body["blockers_count"] == 0
        assert body["last_entry_at"] is None

    def test_streak_counts_consecutive_working_days(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        for offset in (1, 2, 3):
            _seed_entry(
                db,
                employee_user,
                TODAY - timedelta(days=offset),
                items=[(str(uuid4()), "пункт", EntryItemStatus.IN_PROGRESS.value)],
            )

        body = client.get("/api/employee/statistics", headers=employee_headers).json()
        assert body["streak"] == 3

    def test_day_off_does_not_break_streak(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        _seed_entry(db, employee_user, YESTERDAY, items=[(str(uuid4()), "пункт", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, TODAY - timedelta(days=2), day_type=DayType.OFF.value)
        _seed_entry(
            db,
            employee_user,
            TODAY - timedelta(days=3),
            items=[(str(uuid4()), "пункт", EntryItemStatus.IN_PROGRESS.value)],
        )

        body = client.get("/api/employee/statistics", headers=employee_headers).json()
        assert body["streak"] == 2

    def test_chain_counters(self, client, db, employee_headers, employee_user):
        open_chain, blocked_chain, dropped_chain, done_chain = (str(uuid4()) for _ in range(4))
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[
                (open_chain, "идёт", EntryItemStatus.IN_PROGRESS.value),
                (blocked_chain, "ждём смежника", EntryItemStatus.BLOCKED.value),
                (dropped_chain, "отменили", EntryItemStatus.DROPPED.value),
                (done_chain, "готово", EntryItemStatus.DONE.value),
            ],
        )

        body = client.get("/api/employee/statistics", headers=employee_headers).json()
        assert body["open_chains_count"] == 2
        assert body["blockers_count"] == 1
        assert body["dropped_chains_count"] == 1

    def test_completion_rate_is_null_without_schedule(self, client, db, employee_headers, employee_user):
        employee_user.schedule_type = "none"
        employee_user.work_days = None
        db.commit()

        body = client.get("/api/employee/statistics", headers=employee_headers).json()
        assert body["completion_rate"] is None

    def test_completion_rate_counts_scheduled_days_only(self, client, db, employee_headers, employee_user):
        employee_user.work_days = [TODAY.isoweekday()]
        db.commit()
        _seed_entry(db, employee_user, TODAY, items=[(str(uuid4()), "пункт", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, TODAY - timedelta(days=7), day_type=DayType.OFF.value)

        body = client.get("/api/employee/statistics", headers=employee_headers).json()
        assert body["completion_rate"] == 0.25

    def test_completion_rate_is_fraction_of_window(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        for offset in range(12):
            _seed_entry(db, employee_user, TODAY - timedelta(days=offset))

        rate = client.get("/api/employee/statistics", headers=employee_headers).json()["completion_rate"]
        assert rate == 0.4
        assert 0 <= rate <= 1
