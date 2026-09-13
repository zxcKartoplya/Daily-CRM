from datetime import date, datetime, time, timedelta

from app.models.enums import DailyEntryStatus, DayType, UserStatus
from tests.test_analytics_timeseries import _employee, _timeseries
from tests.test_daily_entries import _seed_entry

TODAY = date.today()
WINDOW_DAYS = 30


def _day(offset: int) -> date:
    return TODAY - timedelta(days=offset)


def _overview(client, headers):
    response = client.get("/api/admin/analytics/overview", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestAnalyticsOverviewCompletionRate:
    def test_completion_rate_is_company_fraction_over_window(self, client, admin_headers, db):
        all_week = _employee(db, "AllWeek")
        for offset in range(WINDOW_DAYS):
            _seed_entry(db, all_week, _day(offset))

        one_day = _employee(db, "OneDay", work_days=[TODAY.isoweekday()])
        _seed_entry(db, one_day, TODAY)

        _employee(db, "Unscheduled", schedule_type="none")

        rate = _overview(client, admin_headers)["completion_rate_last_30_days"]
        assert rate == round(31 / 35, 4)
        assert 0 <= rate <= 1

    def test_fully_filled_window_is_one(self, client, admin_headers, db):
        employee = _employee(db, "Diligent")
        for offset in range(WINDOW_DAYS):
            _seed_entry(db, employee, _day(offset))

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] == 1.0

    def test_completion_rate_is_null_without_employees(self, client, admin_headers):
        assert _overview(client, admin_headers)["completion_rate_last_30_days"] is None

    def test_completion_rate_is_null_without_scheduled_employees(self, client, admin_headers, db):
        employee = _employee(db, "Unscheduled", schedule_type="none")
        _seed_entry(db, employee, TODAY)

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] is None

    def test_draft_is_not_submitted(self, client, admin_headers, db):
        employee = _employee(db, "Drafter")
        for offset in range(WINDOW_DAYS):
            status = DailyEntryStatus.SUBMITTED.value if offset % 2 else DailyEntryStatus.DRAFT.value
            _seed_entry(db, employee, _day(offset), status=status)

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] == 0.5

    def test_off_stays_in_denominator(self, client, admin_headers, db):
        employee = _employee(db, "Resting")
        for offset in range(WINDOW_DAYS):
            day_type = DayType.WORK.value if offset % 2 else DayType.OFF.value
            _seed_entry(db, employee, _day(offset), day_type=day_type)

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] == 0.5

    def test_inactive_employee_is_not_counted(self, client, admin_headers, db):
        active = _employee(db, "Active")
        for offset in range(WINDOW_DAYS):
            _seed_entry(db, active, _day(offset))

        inactive = _employee(db, "Inactive")
        inactive.status = UserStatus.INACTIVE.value
        db.commit()

        body = _overview(client, admin_headers)
        assert body["completion_rate_last_30_days"] == 1.0
        assert body["employees_count"] == 1

    def test_employee_hired_inside_window_counts_from_creation(self, client, admin_headers, db):
        newcomer = _employee(db, "Newcomer", created_at=datetime.combine(_day(9), time(12)))
        for offset in range(5):
            _seed_entry(db, newcomer, _day(offset))

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] == 0.5

    def test_completion_rate_matches_timeseries_sum(self, client, admin_headers, db):
        steady = _employee(db, "Steady", work_days=[1, 2, 3, 4, 5])
        for offset in range(0, WINDOW_DAYS, 2):
            _seed_entry(db, steady, _day(offset))

        mixed = _employee(db, "Mixed")
        for offset in range(0, WINDOW_DAYS, 3):
            _seed_entry(db, mixed, _day(offset), status=DailyEntryStatus.DRAFT.value)
        for offset in range(1, WINDOW_DAYS, 3):
            _seed_entry(db, mixed, _day(offset), day_type=DayType.OFF.value)
        _seed_entry(db, mixed, _day(2))

        _employee(db, "Newcomer", created_at=datetime.combine(_day(4), time(12)))

        points = _timeseries(
            client,
            admin_headers,
            date_from=_day(WINDOW_DAYS - 1).isoformat(),
            date_to=TODAY.isoformat(),
        )
        submitted = sum(point["submitted"] for point in points)
        working = sum(point["working_employees"] for point in points)

        assert submitted > 0
        assert _overview(client, admin_headers)["completion_rate_last_30_days"] == round(submitted / working, 4)
