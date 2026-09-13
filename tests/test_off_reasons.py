from datetime import date, timedelta

from app.models.enums import DayType, OffReason
from tests.test_daily_entries import _seed_entry
from tests.test_department_dailies import _department, _employee

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)

EXPECTED_DICTIONARY = [
    {"code": "vacation", "label": "Отпуск", "requires_note": False},
    {"code": "sick_leave", "label": "Больничный", "requires_note": False},
    {"code": "unpaid_leave", "label": "Отгул за свой счёт", "requires_note": False},
    {"code": "business_trip", "label": "Командировка", "requires_note": False},
    {"code": "other", "label": "Другое", "requires_note": True},
]


def _iso(day: date) -> str:
    return day.isoformat()


def _put_day(client, headers, day, **payload):
    return client.put(f"/api/employee/daily/{_iso(day)}", headers=headers, json=payload)


def _seed_day_off(db, user, day, reason=OffReason.VACATION, note=None):
    entry = _seed_entry(db, user, day, day_type=DayType.OFF.value)
    entry.off_reason = reason.value
    entry.off_reason_note = note
    db.commit()
    db.refresh(entry)
    return entry


class TestOffReasonDictionary:
    def test_admin_gets_dictionary(self, client, admin_headers):
        response = client.get("/api/dictionaries/off-reasons", headers=admin_headers)
        assert response.status_code == 200
        assert response.json() == EXPECTED_DICTIONARY

    def test_employee_gets_dictionary(self, client, employee_headers):
        response = client.get("/api/dictionaries/off-reasons", headers=employee_headers)
        assert response.status_code == 200
        assert response.json() == EXPECTED_DICTIONARY

    def test_unauthenticated_returns_401(self, client):
        assert client.get("/api/dictionaries/off-reasons").status_code == 401


class TestOffReasonOnSave:
    def test_reason_is_saved_and_exposed_to_cabinet_and_crm(
        self, client, admin_headers, employee_headers, employee_user
    ):
        saved = _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="sick_leave")
        assert saved.status_code == 200
        body = saved.json()
        assert body["off_reason"] == "sick_leave"
        assert body["off_reason_note"] is None

        view = client.get(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers).json()
        assert view["entry"]["off_reason"] == "sick_leave"

        listed = client.get("/api/employee/daily", headers=employee_headers).json()
        assert [row["off_reason"] for row in listed] == ["sick_leave"]

        reports = client.get("/api/admin/reports", headers=admin_headers).json()
        assert [(row["id"], row["off_reason"]) for row in reports] == [(body["id"], "sick_leave")]

        detail = client.get(f"/api/admin/reports/{body['id']}", headers=admin_headers).json()
        assert detail["off_reason"] == "sick_leave"
        assert detail["off_reason_note"] is None

    def test_other_reason_saves_trimmed_note(self, client, admin_headers, employee_headers, employee_user):
        saved = _put_day(
            client, employee_headers, YESTERDAY, day_type="off", off_reason="other", off_reason_note="  донор крови "
        )
        assert saved.status_code == 200
        assert saved.json()["off_reason"] == "other"
        assert saved.json()["off_reason_note"] == "донор крови"

        detail = client.get(f"/api/admin/reports/{saved.json()['id']}", headers=admin_headers).json()
        assert detail["off_reason_note"] == "донор крови"

    def test_department_dailies_expose_reason(self, client, db, admin_headers):
        department = _department(db)
        worker = _employee(db, department, "Worker")
        _seed_day_off(db, worker, YESTERDAY, OffReason.BUSINESS_TRIP)

        body = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": _iso(YESTERDAY), "date_to": _iso(YESTERDAY)},
        ).json()
        assert body["employees"][0]["days"][0]["entry"]["off_reason"] == "business_trip"

    def test_day_off_without_reason_is_allowed(self, client, employee_headers, employee_user):
        response = _put_day(client, employee_headers, YESTERDAY, day_type="off")
        assert response.status_code == 200
        assert response.json()["off_reason"] is None
        assert response.json()["off_reason_note"] is None

    def test_reason_on_work_day_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(
            client,
            employee_headers,
            TODAY,
            off_reason="vacation",
            items=[{"text": "работаю", "status": "in_progress"}],
        )
        assert response.status_code == 400
        assert client.get("/api/employee/daily", headers=employee_headers).json() == []

    def test_other_without_note_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="other")
        assert response.status_code == 400

    def test_other_with_blank_note_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(
            client, employee_headers, YESTERDAY, day_type="off", off_reason="other", off_reason_note="   "
        )
        assert response.status_code == 400

    def test_note_for_non_other_reason_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(
            client, employee_headers, YESTERDAY, day_type="off", off_reason="vacation", off_reason_note="на море"
        )
        assert response.status_code == 400

    def test_blank_note_for_non_other_reason_is_ignored(self, client, employee_headers, employee_user):
        response = _put_day(
            client, employee_headers, YESTERDAY, day_type="off", off_reason="vacation", off_reason_note="  "
        )
        assert response.status_code == 200
        assert response.json()["off_reason"] == "vacation"
        assert response.json()["off_reason_note"] is None

    def test_note_without_reason_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason_note="просто так")
        assert response.status_code == 400

    def test_too_long_note_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(
            client, employee_headers, YESTERDAY, day_type="off", off_reason="other", off_reason_note="я" * 201
        )
        assert response.status_code == 422

    def test_note_of_max_length_is_accepted(self, client, employee_headers, employee_user):
        response = _put_day(
            client, employee_headers, YESTERDAY, day_type="off", off_reason="other", off_reason_note="я" * 200
        )
        assert response.status_code == 200

    def test_unknown_reason_is_rejected(self, client, employee_headers, employee_user):
        response = _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="holiday")
        assert response.status_code == 422

    def test_switching_to_work_clears_reason(self, client, db, employee_headers, employee_user):
        entry = _seed_day_off(db, employee_user, YESTERDAY, OffReason.OTHER, "переезд")

        response = _put_day(
            client, employee_headers, YESTERDAY, items=[{"text": "всё-таки работал", "status": "done"}]
        )
        assert response.status_code == 200
        assert response.json()["day_type"] == "work"
        assert response.json()["off_reason"] is None
        assert response.json()["off_reason_note"] is None

        db.refresh(entry)
        assert entry.off_reason is None
        assert entry.off_reason_note is None


class TestOffReasonOnBulk:
    def test_bulk_sets_reason_on_all_dates(self, client, db, admin_headers, employee_headers, employee_user):
        _seed_day_off(db, employee_user, YESTERDAY, OffReason.SICK_LEAVE)
        dates = [_iso(TODAY - timedelta(days=offset)) for offset in (1, 2, 3)]

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": dates, "day_type": "off", "off_reason": "vacation"},
        )
        assert response.status_code == 200
        assert sorted((row["date"], row["off_reason"]) for row in response.json()) == sorted(
            (day, "vacation") for day in dates
        )

        reports = client.get("/api/admin/reports", headers=admin_headers).json()
        assert sorted((row["date"], row["off_reason"]) for row in reports) == sorted((day, "vacation") for day in dates)

    def test_bulk_sets_other_with_note(self, client, employee_headers, employee_user):
        dates = [_iso(TODAY - timedelta(days=offset)) for offset in (1, 2)]

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": dates, "day_type": "off", "off_reason": "other", "off_reason_note": "учёба"},
        )
        assert response.status_code == 200
        assert {(row["off_reason"], row["off_reason_note"]) for row in response.json()} == {("other", "учёба")}

    def test_bulk_without_reason_leaves_reason_empty(self, client, employee_headers, employee_user):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200
        assert response.json()[0]["off_reason"] is None

    def test_bulk_other_without_note_is_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off", "off_reason": "other"},
        )
        assert response.status_code == 400
        assert client.get("/api/employee/daily", headers=employee_headers).json() == []

    def test_bulk_note_for_non_other_reason_is_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off", "off_reason": "vacation", "off_reason_note": "x"},
        )
        assert response.status_code == 400


class TestOffReasonEditedAt:
    def test_changing_reason_of_submitted_entry_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry = _seed_day_off(db, employee_user, YESTERDAY, OffReason.VACATION)

        response = _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="sick_leave")
        assert response.status_code == 200
        db.refresh(entry)
        assert entry.edited_at is not None

    def test_same_reason_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry = _seed_day_off(db, employee_user, YESTERDAY, OffReason.VACATION)

        response = _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="vacation")
        assert response.status_code == 200
        db.refresh(entry)
        assert entry.edited_at is None

    def test_changing_note_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry = _seed_day_off(db, employee_user, YESTERDAY, OffReason.OTHER, "переезд")

        _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="other", off_reason_note="  переезд ")
        db.refresh(entry)
        assert entry.edited_at is None

        _put_day(client, employee_headers, YESTERDAY, day_type="off", off_reason="other", off_reason_note="ремонт")
        db.refresh(entry)
        assert entry.edited_at is not None

    def test_bulk_changing_reason_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry = _seed_day_off(db, employee_user, YESTERDAY, OffReason.VACATION)

        client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off", "off_reason": "business_trip"},
        )
        db.refresh(entry)
        assert entry.edited_at is not None

    def test_bulk_same_reason_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry = _seed_day_off(db, employee_user, YESTERDAY, OffReason.VACATION)

        client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off", "off_reason": "vacation"},
        )
        db.refresh(entry)
        assert entry.edited_at is None
