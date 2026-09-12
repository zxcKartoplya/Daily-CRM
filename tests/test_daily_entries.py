from datetime import date, datetime, timedelta
from uuid import uuid4

from app.models import DailyEntry, EntryItem
from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus

TODAY = date.today()
YESTERDAY = TODAY - timedelta(days=1)


def _iso(day: date) -> str:
    return day.isoformat()


def _all_week(db, user):
    user.work_days = [1, 2, 3, 4, 5, 6, 7]
    db.commit()
    db.refresh(user)
    return user


def _seed_entry(db, user, day, *, status=DailyEntryStatus.SUBMITTED.value, day_type=DayType.WORK.value, items=()):
    entry = DailyEntry(
        user_id=user.id,
        department_id=user.department_id,
        date=day,
        day_type=day_type,
        status=status,
        submitted_at=datetime.utcnow() if status == DailyEntryStatus.SUBMITTED.value else None,
    )
    db.add(entry)
    db.flush()
    for position, (chain_id, text, item_status) in enumerate(items):
        db.add(
            EntryItem(
                entry_id=entry.id,
                chain_id=chain_id,
                text=text,
                status=item_status,
                position=position,
            )
        )
    db.commit()
    db.refresh(entry)
    return entry


class TestDayView:
    def test_empty_day_returns_null_entry(self, client, employee_headers, employee_user):
        response = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["entry"] is None
        assert body["open_chains"] == []

    def test_unauthenticated_returns_401(self, client):
        assert client.get(f"/api/employee/daily/{_iso(TODAY)}").status_code == 401

    def test_admin_cannot_use_employee_endpoint(self, client, admin_headers):
        response = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=admin_headers)
        assert response.status_code == 403


class TestSaveDay:
    def test_new_item_gets_chain_id_and_draft_status(self, client, employee_headers, employee_user):
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"text": "перенёс справочники", "status": "in_progress"}]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "draft"
        assert body["day_type"] == "work"
        assert body["submitted_at"] is None
        assert len(body["items"]) == 1
        assert body["items"][0]["chain_id"]
        assert body["items"][0]["position"] == 0

    def test_save_replaces_whole_day(self, client, employee_headers, employee_user):
        first = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={
                "items": [
                    {"text": "пункт A", "status": "in_progress"},
                    {"text": "пункт B", "status": "done"},
                ]
            },
        ).json()
        kept_chain = first["items"][0]["chain_id"]

        second = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": kept_chain, "text": "пункт A, продолжение", "status": "blocked"}]},
        )
        assert second.status_code == 200
        items = second.json()["items"]
        assert len(items) == 1
        assert items[0]["chain_id"] == kept_chain
        assert items[0]["status"] == "blocked"

    def test_continues_chain_from_previous_day(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(chain_id, "начал переносить отчётность", EntryItemStatus.BLOCKED.value)],
        )

        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "архив дали, сошлось", "status": "in_progress"}]},
        )
        assert response.status_code == 200
        assert response.json()["items"][0]["chain_id"] == chain_id

    def test_duplicate_chain_in_one_day_rejected(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "линия", EntryItemStatus.IN_PROGRESS.value)])

        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={
                "items": [
                    {"chain_id": chain_id, "text": "раз", "status": "in_progress"},
                    {"chain_id": chain_id, "text": "два", "status": "done"},
                ]
            },
        )
        assert response.status_code == 400

    def test_unknown_chain_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": str(uuid4()), "text": "ниоткуда", "status": "in_progress"}]},
        )
        assert response.status_code == 404

    def test_other_user_chain_rejected(self, client, db, employee_headers, employee_user, admin_user):
        chain_id = str(uuid4())
        _seed_entry(db, admin_user, YESTERDAY, items=[(chain_id, "чужая линия", EntryItemStatus.IN_PROGRESS.value)])

        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "подхватил чужое", "status": "in_progress"}]},
        )
        assert response.status_code == 404

    def test_day_off_with_items_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"day_type": "off", "items": [{"text": "что-то делал", "status": "in_progress"}]},
        )
        assert response.status_code == 400

    def test_day_off_clears_items(self, client, employee_headers, employee_user):
        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"text": "пункт", "status": "in_progress"}]},
        )
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"day_type": "off", "items": []},
        )
        assert response.status_code == 200
        assert response.json()["day_type"] == "off"
        assert response.json()["items"] == []

    def test_future_day_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY + timedelta(days=1))}",
            headers=employee_headers,
            json={"items": [{"text": "заранее", "status": "in_progress"}]},
        )
        assert response.status_code == 400

    def test_outside_backfill_window_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY - timedelta(days=8))}",
            headers=employee_headers,
            json={"items": [{"text": "поздно вспомнил", "status": "in_progress"}]},
        )
        assert response.status_code == 400

    def test_backfill_inside_window_allowed(self, client, employee_headers, employee_user):
        response = client.put(
            f"/api/employee/daily/{_iso(TODAY - timedelta(days=6))}",
            headers=employee_headers,
            json={"items": [{"text": "дозаполнил", "status": "in_progress"}]},
        )
        assert response.status_code == 200

    def test_submitted_past_day_is_closed(self, client, db, employee_headers, employee_user):
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(str(uuid4()), "вчерашнее", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"text": "переписал историю", "status": "done"}]},
        )
        assert response.status_code == 400

    def test_draft_past_day_stays_editable(self, client, db, employee_headers, employee_user):
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            status=DailyEntryStatus.DRAFT.value,
            items=[(str(uuid4()), "черновик", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"text": "дописал черновик", "status": "in_progress"}]},
        )
        assert response.status_code == 200


class TestSubmitDay:
    def test_submit_sets_status_and_timestamp(self, client, employee_headers, employee_user):
        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"text": "пункт", "status": "in_progress"}]},
        )
        response = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"
        assert response.json()["submitted_at"] is not None

    def test_double_submit_rejected(self, client, employee_headers, employee_user):
        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"text": "пункт", "status": "in_progress"}]},
        )
        client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        response = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        assert response.status_code == 400

    def test_work_day_without_items_rejected(self, client, employee_headers, employee_user):
        client.put(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers, json={"items": []})
        response = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        assert response.status_code == 400

    def test_day_off_submits_without_items(self, client, employee_headers, employee_user):
        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"day_type": "off", "items": []},
        )
        response = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        assert response.status_code == 200

    def test_submit_without_entry_returns_404(self, client, employee_headers, employee_user):
        response = client.post(f"/api/employee/daily/{_iso(TODAY)}/submit", headers=employee_headers)
        assert response.status_code == 404


class TestOpenChains:
    def test_open_chain_carries_title_and_last_update(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(
            db,
            employee_user,
            TODAY - timedelta(days=3),
            items=[(chain_id, "начал переносить отчётность", EntryItemStatus.IN_PROGRESS.value)],
        )
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(chain_id, "жду архив от Ивана", EntryItemStatus.BLOCKED.value)],
        )

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert len(body["open_chains"]) == 1
        chain = body["open_chains"][0]
        assert chain["chain_id"] == chain_id
        assert chain["title"] == "начал переносить отчётность"
        assert chain["last_text"] == "жду архив от Ивана"
        assert chain["last_status"] == "blocked"
        assert chain["last_date"] == _iso(YESTERDAY)
        assert chain["days_open"] == 4

    def test_chain_closed_yesterday_is_gone(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "добил", EntryItemStatus.DONE.value)])

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert body["open_chains"] == []

    def test_chain_closed_today_stays_in_list(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "линия", EntryItemStatus.IN_PROGRESS.value)])
        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "закрыл", "status": "done"}]},
        )

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert [chain["chain_id"] for chain in body["open_chains"]] == [chain_id]
        assert [item["chain_id"] for item in body["entry"]["items"]] == [chain_id]

    def test_dropped_chain_is_gone(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "не будем делать", EntryItemStatus.DROPPED.value)])

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert body["open_chains"] == []


class TestMissingDays:
    def test_working_day_without_entry_is_missing(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert _iso(YESTERDAY) in body["missing_days"]
        assert _iso(TODAY) not in body["missing_days"]

    def test_day_off_is_not_missing(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        _seed_entry(db, employee_user, YESTERDAY, day_type=DayType.OFF.value)

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert _iso(YESTERDAY) not in body["missing_days"]

    def test_schedule_none_has_no_missing_days(self, client, db, employee_headers, employee_user):
        employee_user.schedule_type = "none"
        employee_user.work_days = None
        db.commit()

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert body["missing_days"] == []

    def test_only_scheduled_weekdays_are_missing(self, client, db, employee_headers, employee_user):
        employee_user.work_days = [TODAY.isoweekday()]
        db.commit()

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert body["missing_days"]
        assert all(
            date.fromisoformat(day).isoweekday() == TODAY.isoweekday() for day in body["missing_days"]
        )


class TestChainHistory:
    def test_history_is_ordered_by_date(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, TODAY - timedelta(days=2), items=[(chain_id, "первый", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "второй", EntryItemStatus.DONE.value)])

        response = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers)
        assert response.status_code == 200
        body = response.json()
        assert body["title"] == "первый"
        assert body["last_status"] == "done"
        assert [item["text"] for item in body["items"]] == ["первый", "второй"]
        assert body["first_date"] == _iso(TODAY - timedelta(days=2))

    def test_unknown_chain_returns_404(self, client, employee_headers, employee_user):
        response = client.get(f"/api/employee/daily-chains/{uuid4()}", headers=employee_headers)
        assert response.status_code == 404

    def test_other_user_chain_returns_404(self, client, db, employee_headers, employee_user, admin_user):
        chain_id = str(uuid4())
        _seed_entry(db, admin_user, YESTERDAY, items=[(chain_id, "чужое", EntryItemStatus.IN_PROGRESS.value)])

        response = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers)
        assert response.status_code == 404


class TestEntriesList:
    def test_list_returns_own_entries_in_range(self, client, db, employee_headers, employee_user):
        _seed_entry(db, employee_user, YESTERDAY, items=[(str(uuid4()), "вчера", EntryItemStatus.DONE.value)])
        _seed_entry(db, employee_user, TODAY - timedelta(days=5), items=[(str(uuid4()), "давно", EntryItemStatus.DONE.value)])

        response = client.get(
            "/api/employee/daily",
            headers=employee_headers,
            params={"date_from": _iso(YESTERDAY)},
        )
        assert response.status_code == 200
        assert [entry["date"] for entry in response.json()] == [_iso(YESTERDAY)]
