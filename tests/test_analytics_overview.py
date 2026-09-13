from datetime import date, timedelta

from tests.test_analytics_timeseries import _employee
from tests.test_daily_entries import _seed_entry

TODAY = date.today()


def _day(offset: int) -> date:
    return TODAY - timedelta(days=offset)


def _overview(client, headers):
    response = client.get("/api/admin/analytics/overview", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


class TestAnalyticsOverviewCompletionRate:
    def test_completion_rate_is_fraction_averaged_over_employees(self, client, admin_headers, db):
        all_week = _employee(db, "AllWeek")
        for offset in range(9):
            _seed_entry(db, all_week, _day(offset))

        one_day = _employee(db, "OneDay", work_days=[TODAY.isoweekday()])
        for offset in (0, 7, 14, 21):
            _seed_entry(db, one_day, _day(offset))

        _employee(db, "Unscheduled", schedule_type="none")

        rate = _overview(client, admin_headers)["completion_rate_last_30_days"]
        assert rate == 0.55
        assert 0 <= rate <= 1

    def test_fully_filled_window_is_one(self, client, admin_headers, db):
        employee = _employee(db, "Diligent")
        for offset in range(30):
            _seed_entry(db, employee, _day(offset))

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] == 1.0

    def test_completion_rate_is_null_without_employees(self, client, admin_headers):
        assert _overview(client, admin_headers)["completion_rate_last_30_days"] is None

    def test_completion_rate_is_null_without_scheduled_employees(self, client, admin_headers, db):
        employee = _employee(db, "Unscheduled", schedule_type="none")
        _seed_entry(db, employee, TODAY)

        assert _overview(client, admin_headers)["completion_rate_last_30_days"] is None
