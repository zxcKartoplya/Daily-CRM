from datetime import date, datetime, timedelta
from uuid import uuid4

from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus
from tests.test_daily_entries import _seed_entry
from tests.test_department_dailies import _department, _employee

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _iso(day: date) -> str:
    return day.isoformat()


def _seed_two_items(db, user, day, *, status=DailyEntryStatus.SUBMITTED.value):
    first, second = str(uuid4()), str(uuid4())
    entry = _seed_entry(
        db,
        user,
        day,
        status=status,
        items=[
            (first, "первый пункт", EntryItemStatus.IN_PROGRESS.value),
            (second, "второй пункт", EntryItemStatus.DONE.value),
        ],
    )
    return entry, first, second


def _same_items(first, second):
    return [
        {"chain_id": first, "text": "первый пункт", "status": "in_progress"},
        {"chain_id": second, "text": "второй пункт", "status": "done"},
    ]


def _edited_at(db, entry):
    db.refresh(entry)
    return entry.edited_at


class TestEditedAtOnSave:
    def test_editing_submitted_entry_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry, first, second = _seed_two_items(db, employee_user, YESTERDAY)
        items = _same_items(first, second)
        items[0]["text"] = "первый пункт, уточнил"

        response = client.put(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers, json={"items": items})
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"
        assert _edited_at(db, entry) is not None

    def test_same_content_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry, first, second = _seed_two_items(db, employee_user, YESTERDAY)

        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": _same_items(first, second)},
        )
        assert response.status_code == 200
        assert _edited_at(db, entry) is None

    def test_repeated_save_without_changes_keeps_edited_at(self, client, db, employee_headers, employee_user):
        entry, first, second = _seed_two_items(db, employee_user, YESTERDAY)
        items = _same_items(first, second)
        items[1]["status"] = "blocked"

        client.put(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers, json={"items": items})
        marked = _edited_at(db, entry)
        assert marked is not None

        response = client.put(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers, json={"items": items})
        assert response.status_code == 200
        assert _edited_at(db, entry) == marked

    def test_reordering_items_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry, first, second = _seed_two_items(db, employee_user, YESTERDAY)

        client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": list(reversed(_same_items(first, second)))},
        )
        assert _edited_at(db, entry) is not None

    def test_adding_link_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry, first, second = _seed_two_items(db, employee_user, YESTERDAY)
        items = _same_items(first, second)
        items[0]["link"] = "https://tracker.example/TASK-1"

        client.put(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers, json={"items": items})
        assert _edited_at(db, entry) is not None

    def test_changing_day_type_sets_edited_at(self, client, db, employee_headers, employee_user):
        entry, _, _ = _seed_two_items(db, employee_user, YESTERDAY)

        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"day_type": "off", "items": []},
        )
        assert response.status_code == 200
        assert _edited_at(db, entry) is not None

    def test_editing_draft_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry, first, second = _seed_two_items(db, employee_user, YESTERDAY, status=DailyEntryStatus.DRAFT.value)
        items = _same_items(first, second)
        items[0]["text"] = "дописал черновик"

        client.put(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers, json={"items": items})
        assert _edited_at(db, entry) is None

    def test_submit_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry, _, _ = _seed_two_items(db, employee_user, TODAY, status=DailyEntryStatus.DRAFT.value)

        response = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        assert response.status_code == 200
        assert _edited_at(db, entry) is None

    def test_rejected_edit_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry, _, _ = _seed_two_items(db, employee_user, YESTERDAY)

        response = client.put(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers, json={"items": []})
        assert response.status_code == 400
        assert _edited_at(db, entry) is None


class TestEditedAtOnBulk:
    def test_bulk_overwriting_submitted_work_day_sets_edited_at(
        self, client, db, admin_headers, employee_headers, employee_user
    ):
        entry, _, _ = _seed_two_items(db, employee_user, YESTERDAY)
        target = TODAY - timedelta(days=2)

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(target), _iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200
        assert _edited_at(db, entry) is not None

        admin_entries = {row["date"]: row for row in client.get("/api/admin/reports", headers=admin_headers).json()}
        assert admin_entries[_iso(target)]["edited_at"] is None

    def test_bulk_over_submitted_day_off_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry = _seed_entry(db, employee_user, YESTERDAY, day_type=DayType.OFF.value)

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200
        assert _edited_at(db, entry) is None

    def test_bulk_over_draft_does_not_set_edited_at(self, client, db, employee_headers, employee_user):
        entry, _, _ = _seed_two_items(db, employee_user, YESTERDAY, status=DailyEntryStatus.DRAFT.value)

        client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        assert _edited_at(db, entry) is None

    def test_bulk_over_submitted_day_keeps_original_submitted_at(self, client, db, employee_headers, employee_user):
        entry, _, _ = _seed_two_items(db, employee_user, YESTERDAY)
        original = datetime(2020, 1, 1, 9, 30)
        entry.submitted_at = original
        db.commit()

        client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        db.refresh(entry)
        assert entry.submitted_at == original
        assert entry.edited_at is not None

    def test_bulk_over_draft_sets_submitted_at(self, client, db, employee_headers, employee_user):
        entry, _, _ = _seed_two_items(db, employee_user, YESTERDAY, status=DailyEntryStatus.DRAFT.value)
        entry.submitted_at = None
        db.commit()

        client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        db.refresh(entry)
        assert entry.status == DailyEntryStatus.SUBMITTED.value
        assert entry.submitted_at is not None


class TestEditedAtVisibility:
    def _edited_entry(self, db, user, day=YESTERDAY):
        entry, _, _ = _seed_two_items(db, user, day)
        entry.edited_at = datetime.utcnow()
        db.commit()
        db.refresh(entry)
        return entry

    def test_admin_reports_list_exposes_edited_at(self, client, db, admin_headers, employee_user):
        self._edited_entry(db, employee_user)
        untouched, _, _ = _seed_two_items(db, employee_user, TODAY - timedelta(days=2))

        response = client.get("/api/admin/reports", headers=admin_headers)
        assert response.status_code == 200
        by_id = {row["id"]: row for row in response.json()}
        assert by_id[untouched.id]["edited_at"] is None
        assert all("submitted_at" in row for row in by_id.values())
        assert sum(row["edited_at"] is not None for row in by_id.values()) == 1

    def test_admin_report_detail_exposes_edited_at(self, client, db, admin_headers, employee_user):
        entry = self._edited_entry(db, employee_user)

        response = client.get(f"/api/admin/reports/{entry.id}", headers=admin_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["edited_at"] is not None
        assert body["submitted_at"] is not None

    def test_department_dailies_expose_edited_at(self, client, db, admin_headers):
        department = _department(db)
        worker = _employee(db, department, "Worker")
        self._edited_entry(db, worker)

        body = client.get(
            f"/api/admin/departments/{department.id}/dailies",
            headers=admin_headers,
            params={"date_from": _iso(YESTERDAY), "date_to": _iso(YESTERDAY)},
        ).json()
        assert body["employees"][0]["days"][0]["entry"]["edited_at"] is not None

    def test_employee_responses_have_no_edited_at(self, client, db, employee_headers, employee_user):
        entry = self._edited_entry(db, employee_user)

        listed = client.get("/api/employee/daily", headers=employee_headers).json()
        assert listed and all("edited_at" not in row for row in listed)

        view = client.get(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers).json()
        assert view["entry"]["id"] == entry.id
        assert "edited_at" not in view["entry"]

        saved = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"text": "поправил", "status": "done"}]},
        ).json()
        assert "edited_at" not in saved

        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"text": "сегодня", "status": "in_progress"}]},
        )
        submitted = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers).json()
        assert "edited_at" not in submitted

        bulk = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(TODAY - timedelta(days=3))], "day_type": "off"},
        ).json()
        assert bulk and all("edited_at" not in row for row in bulk)
