from datetime import date, timedelta
from uuid import uuid4

from app.core.security import create_access_token, hash_password
from app.models import EntryItem, User
from app.models.enums import EntryItemStatus, UserRole, UserStatus
from tests.test_daily_entries import _seed_entry

TODAY = date.today()
END = TODAY - timedelta(days=60)

IN_PROGRESS = EntryItemStatus.IN_PROGRESS.value
BLOCKED = EntryItemStatus.BLOCKED.value
DONE = EntryItemStatus.DONE.value
DROPPED = EntryItemStatus.DROPPED.value


def _day(offset: int) -> date:
    return END + timedelta(days=offset)


def _seed_chains(db, user, chains: dict[str, list[tuple[int, str]]]) -> None:
    by_day: dict[date, list[tuple[str, str, str]]] = {}
    for chain_id, points in chains.items():
        for offset, item_status in points:
            by_day.setdefault(_day(offset), []).append((chain_id, f"шаг {offset}", item_status))
    for day in sorted(by_day):
        _seed_entry(db, user, day, items=by_day[day])


def _activity(client, headers, **params):
    return client.get("/api/employee/activity", headers=headers, params=params)


def _chains_by_id(body) -> dict[str, dict]:
    return {chain["chain_id"]: chain for chain in body["chains"]}


def _history(points: list[tuple[int, str]]) -> list[dict]:
    return [{"date": _day(offset).isoformat(), "status": item_status} for offset, item_status in points]


class TestActivityPeriod:
    def test_week_covers_seven_days(self, client, employee_headers, employee_user):
        response = _activity(client, employee_headers, period="week", date=END.isoformat())
        assert response.status_code == 200
        body = response.json()
        assert body["period"] == "week"
        assert body["date_from"] == _day(-6).isoformat()
        assert body["date_to"] == END.isoformat()
        assert body["chains"] == []
        assert body["summary"] == {
            "chains_count": 0,
            "started_count": 0,
            "done_count": 0,
            "dropped_count": 0,
            "open_count": 0,
            "blocked_chains_count": 0,
            "blocked_days": 0,
            "avg_days_to_done": None,
        }

    def test_month_covers_thirty_days(self, client, employee_headers, employee_user):
        body = _activity(client, employee_headers, period="month", date=END.isoformat()).json()
        assert body["period"] == "month"
        assert body["date_from"] == _day(-29).isoformat()
        assert body["date_to"] == END.isoformat()

    def test_defaults_to_week_ending_today(self, client, employee_headers, employee_user):
        body = _activity(client, employee_headers).json()
        assert body["period"] == "week"
        assert body["date_to"] == TODAY.isoformat()
        assert body["date_from"] == (TODAY - timedelta(days=6)).isoformat()

    def test_future_date_rejected(self, client, employee_headers, employee_user):
        response = _activity(client, employee_headers, date=(TODAY + timedelta(days=1)).isoformat())
        assert response.status_code == 422

    def test_unknown_period_rejected(self, client, employee_headers, employee_user):
        assert _activity(client, employee_headers, period="year").status_code == 422


class TestActivityChains:
    def test_chain_done_in_period(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        points = [(-10, IN_PROGRESS), (-8, BLOCKED), (-3, DONE)]
        _seed_chains(db, employee_user, {chain_id: points})
        first_item = (
            db.query(EntryItem).filter(EntryItem.chain_id == chain_id).order_by(EntryItem.id.asc()).first()
        )
        first_item.link = "https://tracker/TASK-1"
        db.commit()

        body = _activity(client, employee_headers, date=END.isoformat()).json()
        assert body["chains"] == [
            {
                "chain_id": chain_id,
                "title": "шаг -10",
                "link": "https://tracker/TASK-1",
                "first_date": _day(-10).isoformat(),
                "last_date": _day(-3).isoformat(),
                "last_status": DONE,
                "outcome": "done",
                "closed_date": _day(-3).isoformat(),
                "days_total": 8,
                "blocked_days": 1,
                "started_in_period": False,
                "closed_in_period": True,
                "history": _history(points),
            }
        ]

    def test_dropped_chain(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_chains(db, employee_user, {chain_id: [(-2, IN_PROGRESS), (-1, DROPPED)]})

        chain = _activity(client, employee_headers, date=END.isoformat()).json()["chains"][0]
        assert chain["outcome"] == "dropped"
        assert chain["last_status"] == DROPPED
        assert chain["closed_date"] == _day(-1).isoformat()
        assert chain["days_total"] == 2
        assert chain["blocked_days"] == 0
        assert chain["started_in_period"] is True
        assert chain["closed_in_period"] is True

    def test_open_chain_with_blocked_days(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_chains(
            db,
            employee_user,
            {chain_id: [(-5, IN_PROGRESS), (-4, BLOCKED), (-3, BLOCKED), (-1, IN_PROGRESS)]},
        )

        chain = _activity(client, employee_headers, date=END.isoformat()).json()["chains"][0]
        assert chain["outcome"] == "open"
        assert chain["last_status"] == IN_PROGRESS
        assert chain["last_date"] == _day(-1).isoformat()
        assert chain["closed_date"] is None
        assert chain["days_total"] == 6
        assert chain["blocked_days"] == 2
        assert chain["started_in_period"] is True
        assert chain["closed_in_period"] is False

    def test_hanging_open_chain_without_items_in_period(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_chains(db, employee_user, {chain_id: [(-20, IN_PROGRESS), (-15, BLOCKED)]})

        body = _activity(client, employee_headers, date=END.isoformat()).json()
        assert [chain["chain_id"] for chain in body["chains"]] == [chain_id]
        chain = body["chains"][0]
        assert chain["first_date"] == _day(-20).isoformat()
        assert chain["last_date"] == _day(-15).isoformat()
        assert chain["days_total"] == 21
        assert chain["blocked_days"] == 1
        assert chain["started_in_period"] is False
        assert body["summary"]["open_count"] == 1
        assert body["summary"]["blocked_chains_count"] == 0
        assert body["summary"]["blocked_days"] == 0

    def test_chain_closed_before_period_excluded(self, client, db, employee_headers, employee_user):
        closed_before, closed_on_start = str(uuid4()), str(uuid4())
        _seed_chains(
            db,
            employee_user,
            {
                closed_before: [(-12, IN_PROGRESS), (-7, DONE)],
                closed_on_start: [(-12, IN_PROGRESS), (-6, DONE)],
            },
        )

        body = _activity(client, employee_headers, date=END.isoformat()).json()
        assert [chain["chain_id"] for chain in body["chains"]] == [closed_on_start]

    def test_chain_started_after_date_to_excluded(self, client, db, employee_headers, employee_user):
        _seed_chains(db, employee_user, {str(uuid4()): [(1, IN_PROGRESS)]})

        body = _activity(client, employee_headers, date=END.isoformat()).json()
        assert body["chains"] == []
        assert body["summary"]["chains_count"] == 0

    def test_past_period_ignores_later_items(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_chains(
            db,
            employee_user,
            {chain_id: [(-3, IN_PROGRESS), (-1, BLOCKED), (1, BLOCKED), (2, DONE)]},
        )

        past = _activity(client, employee_headers, date=END.isoformat()).json()
        chain = past["chains"][0]
        assert chain["last_status"] == BLOCKED
        assert chain["outcome"] == "open"
        assert chain["last_date"] == _day(-1).isoformat()
        assert chain["closed_date"] is None
        assert chain["days_total"] == 4
        assert chain["blocked_days"] == 1
        assert chain["closed_in_period"] is False
        assert chain["history"] == _history([(-3, IN_PROGRESS), (-1, BLOCKED)])
        assert past["summary"]["open_count"] == 1
        assert past["summary"]["done_count"] == 0

        later = _activity(client, employee_headers, date=_day(2).isoformat()).json()["chains"][0]
        assert later["outcome"] == "done"
        assert later["closed_date"] == _day(2).isoformat()
        assert later["days_total"] == 6
        assert later["blocked_days"] == 2

    def test_summary_on_mixed_data(self, client, db, employee_headers, employee_user):
        done_long, done_blocked, done_same_day = (str(uuid4()) for _ in range(3))
        dropped, blocked_open, hanging = (str(uuid4()) for _ in range(3))
        closed_before, started_after = str(uuid4()), str(uuid4())
        _seed_chains(
            db,
            employee_user,
            {
                done_long: [(-10, IN_PROGRESS), (-4, DONE)],
                done_blocked: [(-2, IN_PROGRESS), (-1, BLOCKED), (0, DONE)],
                done_same_day: [(-2, DONE)],
                dropped: [(-5, IN_PROGRESS), (-3, DROPPED)],
                blocked_open: [(-8, BLOCKED), (-6, BLOCKED), (-5, BLOCKED)],
                hanging: [(-15, IN_PROGRESS)],
                closed_before: [(-9, DONE)],
                started_after: [(1, IN_PROGRESS)],
            },
        )

        body = _activity(client, employee_headers, date=END.isoformat()).json()
        assert body["summary"] == {
            "chains_count": 6,
            "started_count": 3,
            "done_count": 3,
            "dropped_count": 1,
            "open_count": 2,
            "blocked_chains_count": 2,
            "blocked_days": 3,
            "avg_days_to_done": 3.7,
        }
        assert [chain["chain_id"] for chain in body["chains"]] == [
            hanging,
            done_long,
            blocked_open,
            dropped,
            *sorted([done_blocked, done_same_day]),
        ]
        assert _chains_by_id(body)[blocked_open]["blocked_days"] == 3


class TestActivityAccess:
    def test_other_employee_chains_hidden(self, client, db, employee_headers, employee_user):
        other = User(
            name="Other Employee",
            email="other@test.com",
            password_hash=hash_password("otherpass"),
            role=UserRole.EMPLOYEE.value,
            status=UserStatus.ACTIVE.value,
        )
        db.add(other)
        db.commit()
        db.refresh(other)
        own_chain, other_chain = str(uuid4()), str(uuid4())
        _seed_chains(db, employee_user, {own_chain: [(-1, IN_PROGRESS)]})
        _seed_chains(db, other, {other_chain: [(-1, BLOCKED)]})

        body = _activity(client, employee_headers, date=END.isoformat()).json()
        assert [chain["chain_id"] for chain in body["chains"]] == [own_chain]

        other_headers = {"Authorization": f"Bearer {create_access_token(other.id, other.email, other.role)}"}
        other_body = _activity(client, other_headers, date=END.isoformat()).json()
        assert [chain["chain_id"] for chain in other_body["chains"]] == [other_chain]

    def test_admin_forbidden(self, client, admin_headers):
        assert _activity(client, admin_headers).status_code == 403

    def test_unauthenticated(self, client):
        assert client.get("/api/employee/activity").status_code == 401
