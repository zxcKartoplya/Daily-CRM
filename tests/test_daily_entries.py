from datetime import date, datetime, timedelta
from uuid import uuid4

from app.models import DailyEntry, EntryItem
from app.models.enums import DailyEntryStatus, DayType, EntryItemStatus, OffReason
from app.services.daily_entries import backfill_window_days

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

    def test_submitted_past_day_inside_window_is_editable(self, client, db, employee_headers, employee_user):
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(str(uuid4()), "вчерашнее", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"text": "уточнил вчерашнее", "status": "done"}]},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "submitted"
        assert body["submitted_at"] is not None
        assert [item["text"] for item in body["items"]] == ["уточнил вчерашнее"]

    def test_submitted_work_day_cannot_be_emptied(self, client, db, employee_headers, employee_user):
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(str(uuid4()), "вчерашнее", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": []},
        )
        assert response.status_code == 400
        items = client.get(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers).json()["entry"]["items"]
        assert [item["text"] for item in items] == ["вчерашнее"]

    def test_submitted_day_on_window_edge_is_editable(self, client, db, employee_headers, employee_user):
        edge = TODAY - timedelta(days=backfill_window_days())
        _seed_entry(
            db,
            employee_user,
            edge,
            items=[(str(uuid4()), "край окна", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.put(
            f"/api/employee/daily/{_iso(edge)}",
            headers=employee_headers,
            json={"items": [{"text": "поправил на краю окна", "status": "done"}]},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "submitted"

    def test_submitted_day_outside_window_is_closed(self, client, db, employee_headers, employee_user):
        outside = TODAY - timedelta(days=backfill_window_days() + 1)
        _seed_entry(
            db,
            employee_user,
            outside,
            items=[(str(uuid4()), "старое", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.put(
            f"/api/employee/daily/{_iso(outside)}",
            headers=employee_headers,
            json={"items": [{"text": "переписал историю", "status": "done"}]},
        )
        assert response.status_code == 400

    def test_submitted_past_day_resubmit_still_rejected(self, client, db, employee_headers, employee_user):
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(str(uuid4()), "вчерашнее", EntryItemStatus.IN_PROGRESS.value)],
        )
        response = client.post(f"/api/employee/daily/{_iso(YESTERDAY)}/submit", headers=employee_headers)
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


class TestChainPoints:
    def test_open_chain_carries_history(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(
            db,
            employee_user,
            TODAY - timedelta(days=2),
            items=[(chain_id, "начал перенос", EntryItemStatus.IN_PROGRESS.value)],
        )
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(chain_id, "жду архив", EntryItemStatus.BLOCKED.value)],
        )

        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        history = body["open_chains"][0]["history"]
        assert [point["date"] for point in history] == [_iso(TODAY - timedelta(days=2)), _iso(YESTERDAY)]
        assert [point["status"] for point in history] == ["in_progress", "blocked"]


class TestEditableWindow:
    def test_day_view_returns_backfill_boundary(self, client, employee_headers, employee_user):
        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert body["editable_from"] == _iso(TODAY - timedelta(days=backfill_window_days()))

    def test_today_is_editable(self, client, employee_headers, employee_user):
        body = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert body["editable"] is True
        assert body["editable_until"] == _iso(TODAY + timedelta(days=backfill_window_days()))

    def test_submitted_past_day_inside_window_is_editable(self, client, db, employee_headers, employee_user):
        _seed_entry(db, employee_user, YESTERDAY, items=[(str(uuid4()), "вчера", EntryItemStatus.DONE.value)])

        body = client.get(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers).json()
        assert body["entry"]["status"] == "submitted"
        assert body["editable"] is True
        assert body["editable_until"] == _iso(YESTERDAY + timedelta(days=backfill_window_days()))

    def test_window_edge_day_is_editable(self, client, employee_headers, employee_user):
        edge = TODAY - timedelta(days=backfill_window_days())
        body = client.get(f"/api/employee/daily/{_iso(edge)}", headers=employee_headers).json()
        assert body["editable"] is True
        assert body["editable_until"] == _iso(TODAY)

    def test_day_outside_window_is_not_editable(self, client, employee_headers, employee_user):
        outside = TODAY - timedelta(days=backfill_window_days() + 1)
        body = client.get(f"/api/employee/daily/{_iso(outside)}", headers=employee_headers).json()
        assert body["editable"] is False
        assert body["editable_until"] == _iso(outside + timedelta(days=backfill_window_days()))

    def test_future_day_is_not_editable(self, client, employee_headers, employee_user):
        future = TODAY + timedelta(days=1)
        body = client.get(f"/api/employee/daily/{_iso(future)}", headers=employee_headers).json()
        assert body["editable"] is False


class TestBulkDaysOff:
    def test_marks_several_days_off_as_submitted(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        days = [_iso(YESTERDAY), _iso(TODAY - timedelta(days=2))]

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": days, "day_type": "off"},
        )
        assert response.status_code == 200
        body = response.json()
        assert [entry["date"] for entry in body] == sorted(days)
        assert all(entry["day_type"] == "off" for entry in body)
        assert all(entry["status"] == "submitted" for entry in body)
        assert all(entry["submitted_at"] is not None for entry in body)

        view = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert all(day not in view["missing_days"] for day in days)

    def test_duplicate_dates_collapse(self, client, employee_headers, employee_user):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY), _iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200
        assert len(response.json()) == 1

    def test_existing_draft_loses_items(self, client, db, employee_headers, employee_user):
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            status=DailyEntryStatus.DRAFT.value,
            items=[(str(uuid4()), "черновик", EntryItemStatus.IN_PROGRESS.value)],
        )

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200
        assert response.json()[0]["items"] == []

    def test_outside_window_rejects_whole_batch(self, client, employee_headers, employee_user):
        outside = TODAY - timedelta(days=60)
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY), _iso(outside)], "day_type": "off"},
        )
        assert response.status_code == 400

        view = client.get(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers).json()
        assert view["entry"] is None

    def test_submitted_past_day_inside_window_is_overwritten(self, client, db, employee_headers, employee_user):
        _seed_entry(db, employee_user, YESTERDAY, items=[(str(uuid4()), "работал", EntryItemStatus.DONE.value)])
        target = TODAY - timedelta(days=2)

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(target), _iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200
        body = response.json()
        assert [entry["date"] for entry in body] == [_iso(target), _iso(YESTERDAY)]
        assert all(entry["day_type"] == "off" for entry in body)
        assert all(entry["items"] == [] for entry in body)

    def test_submitted_day_outside_window_rejects_whole_batch(self, client, db, employee_headers, employee_user):
        outside = TODAY - timedelta(days=backfill_window_days() + 1)
        _seed_entry(db, employee_user, outside, items=[(str(uuid4()), "давно", EntryItemStatus.DONE.value)])

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(outside), _iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 400

        view = client.get(f"/api/employee/daily/{_iso(YESTERDAY)}", headers=employee_headers).json()
        assert view["entry"] is None

    def test_work_day_type_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "work"},
        )
        assert response.status_code == 400

    def test_empty_dates_rejected(self, client, employee_headers, employee_user):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [], "day_type": "off"},
        )
        assert response.status_code == 400

    def test_admin_cannot_use_bulk(self, client, admin_headers):
        response = client.put(
            "/api/employee/daily-bulk",
            headers=admin_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 403


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

    def _list(self, client, headers, **params):
        response = client.get("/api/employee/daily", headers=headers, params=params)
        assert response.status_code == 200
        return response.json()

    def _seed_items(self, db, entry, items):
        for position, chain_id, text, item_status, link in items:
            db.add(
                EntryItem(
                    entry_id=entry.id,
                    chain_id=chain_id,
                    text=text,
                    status=item_status,
                    link=link,
                    position=position,
                )
            )
        db.commit()
        db.refresh(entry)
        return entry

    def test_items_carry_chain_fields(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        entry = _seed_entry(db, employee_user, YESTERDAY)
        self._seed_items(db, entry, [(0, chain_id, "задача", EntryItemStatus.BLOCKED.value, "https://tracker/1")])

        entries = self._list(client, employee_headers)
        assert len(entries) == 1
        [item] = entries[0]["items"]
        assert item["chain_id"] == chain_id
        assert item["text"] == "задача"
        assert item["status"] == "blocked"
        assert item["link"] == "https://tracker/1"
        assert item["position"] == 0
        assert isinstance(item["id"], int)

    def test_all_entry_kinds_are_returned(self, client, db, employee_headers, employee_user):
        submitted_day = TODAY - timedelta(days=1)
        draft_day = TODAY - timedelta(days=2)
        vacation_day = TODAY - timedelta(days=3)
        other_day = TODAY - timedelta(days=4)
        bare_off_day = TODAY - timedelta(days=5)
        _seed_entry(db, employee_user, submitted_day, items=[(str(uuid4()), "сдано", EntryItemStatus.DONE.value)])
        _seed_entry(
            db,
            employee_user,
            draft_day,
            status=DailyEntryStatus.DRAFT.value,
            items=[(str(uuid4()), "черновик", EntryItemStatus.IN_PROGRESS.value)],
        )
        vacation = _seed_entry(db, employee_user, vacation_day, day_type=DayType.OFF.value)
        vacation.off_reason = OffReason.VACATION.value
        other = _seed_entry(db, employee_user, other_day, day_type=DayType.OFF.value)
        other.off_reason = OffReason.OTHER.value
        other.off_reason_note = "переезд"
        _seed_entry(db, employee_user, bare_off_day, day_type=DayType.OFF.value)
        db.commit()

        by_date = {entry["date"]: entry for entry in self._list(client, employee_headers)}
        assert set(by_date) == {_iso(day) for day in (submitted_day, draft_day, vacation_day, other_day, bare_off_day)}

        submitted = by_date[_iso(submitted_day)]
        assert (submitted["day_type"], submitted["status"]) == ("work", "submitted")
        assert submitted["submitted_at"] is not None
        assert [item["text"] for item in submitted["items"]] == ["сдано"]

        draft = by_date[_iso(draft_day)]
        assert (draft["day_type"], draft["status"]) == ("work", "draft")
        assert draft["submitted_at"] is None
        assert [item["text"] for item in draft["items"]] == ["черновик"]

        vacation_entry = by_date[_iso(vacation_day)]
        assert vacation_entry["day_type"] == "off"
        assert vacation_entry["off_reason"] == "vacation"
        assert vacation_entry["off_reason_note"] is None
        assert vacation_entry["items"] == []

        other_entry = by_date[_iso(other_day)]
        assert other_entry["off_reason"] == "other"
        assert other_entry["off_reason_note"] == "переезд"

        bare_off = by_date[_iso(bare_off_day)]
        assert bare_off["day_type"] == "off"
        assert bare_off["off_reason"] is None
        assert bare_off["items"] == []

    def test_entries_by_date_desc_and_items_by_position(self, client, db, employee_headers, employee_user):
        for offset in (3, 1, 2):
            entry = _seed_entry(db, employee_user, TODAY - timedelta(days=offset))
            self._seed_items(
                db,
                entry,
                [
                    (2, str(uuid4()), "третий", EntryItemStatus.DONE.value, None),
                    (0, str(uuid4()), "первый", EntryItemStatus.IN_PROGRESS.value, None),
                    (1, str(uuid4()), "второй", EntryItemStatus.BLOCKED.value, None),
                ],
            )

        entries = self._list(client, employee_headers)
        assert [entry["date"] for entry in entries] == [_iso(TODAY - timedelta(days=offset)) for offset in (1, 2, 3)]
        for entry in entries:
            assert [item["position"] for item in entry["items"]] == [0, 1, 2]
            assert [item["text"] for item in entry["items"]] == ["первый", "второй", "третий"]

    def test_range_bounds_are_inclusive(self, client, db, employee_headers, employee_user):
        date_from = TODAY - timedelta(days=6)
        date_to = TODAY - timedelta(days=2)
        for day in (date_from - timedelta(days=1), date_from, date_to, date_to + timedelta(days=1)):
            _seed_entry(db, employee_user, day, day_type=DayType.OFF.value)

        entries = self._list(client, employee_headers, date_from=_iso(date_from), date_to=_iso(date_to))
        assert [entry["date"] for entry in entries] == [_iso(date_to), _iso(date_from)]

    def test_no_hidden_depth_limit(self, client, db, employee_headers, employee_user):
        quarter_ago = TODAY - timedelta(days=90)
        long_ago = TODAY - timedelta(days=400)
        _seed_entry(db, employee_user, YESTERDAY, items=[(str(uuid4()), "вчера", EntryItemStatus.DONE.value)])
        _seed_entry(db, employee_user, quarter_ago, items=[(str(uuid4()), "квартал", EntryItemStatus.DONE.value)])
        _seed_entry(db, employee_user, long_ago, items=[(str(uuid4()), "давно", EntryItemStatus.DONE.value)])
        expected = [_iso(YESTERDAY), _iso(quarter_ago), _iso(long_ago)]

        assert [entry["date"] for entry in self._list(client, employee_headers)] == expected
        assert [
            entry["date"] for entry in self._list(client, employee_headers, date_from=_iso(long_ago), date_to=_iso(TODAY))
        ] == expected
        assert [entry["date"] for entry in self._list(client, employee_headers, date_from=_iso(quarter_ago))] == expected[:2]

    def test_only_date_to_filters_upper_bound(self, client, db, employee_headers, employee_user):
        long_ago = TODAY - timedelta(days=400)
        for day in (YESTERDAY, TODAY - timedelta(days=5), long_ago):
            _seed_entry(db, employee_user, day, day_type=DayType.OFF.value)

        entries = self._list(client, employee_headers, date_to=_iso(TODAY - timedelta(days=5)))
        assert [entry["date"] for entry in entries] == [_iso(TODAY - timedelta(days=5)), _iso(long_ago)]

    def test_inverted_range_returns_empty_list(self, client, db, employee_headers, employee_user):
        for offset in (1, 2, 3):
            _seed_entry(db, employee_user, TODAY - timedelta(days=offset), day_type=DayType.OFF.value)

        entries = self._list(
            client,
            employee_headers,
            date_from=_iso(TODAY - timedelta(days=1)),
            date_to=_iso(TODAY - timedelta(days=3)),
        )
        assert entries == []

    def test_other_users_entries_and_edited_at_are_hidden(self, client, db, employee_headers, employee_user, admin_user):
        own = _seed_entry(db, employee_user, YESTERDAY, items=[(str(uuid4()), "своё", EntryItemStatus.DONE.value)])
        own.edited_at = datetime.utcnow()
        _seed_entry(db, admin_user, YESTERDAY, items=[(str(uuid4()), "чужое", EntryItemStatus.DONE.value)])
        _seed_entry(db, admin_user, TODAY - timedelta(days=2), day_type=DayType.OFF.value)
        db.commit()

        entries = self._list(client, employee_headers)
        assert [(entry["date"], entry["user_id"]) for entry in entries] == [(_iso(YESTERDAY), employee_user.id)]
        assert [item["text"] for item in entries[0]["items"]] == ["своё"]
        assert "edited_at" not in entries[0]

    def test_chain_across_period_is_restored_by_chain_id(self, client, db, employee_headers, employee_user):
        long_chain = str(uuid4())
        short_chain = str(uuid4())
        first_day = TODAY - timedelta(days=4)
        _seed_entry(
            db,
            employee_user,
            first_day,
            items=[(long_chain, "интеграция", EntryItemStatus.IN_PROGRESS.value)],
        )
        _seed_entry(
            db,
            employee_user,
            TODAY - timedelta(days=3),
            items=[
                (short_chain, "созвон", EntryItemStatus.DONE.value),
                (long_chain, "жду доступы", EntryItemStatus.BLOCKED.value),
            ],
        )
        _seed_entry(db, employee_user, TODAY - timedelta(days=2), day_type=DayType.OFF.value)
        _seed_entry(
            db,
            employee_user,
            YESTERDAY,
            items=[(long_chain, "интеграция готова", EntryItemStatus.DONE.value)],
        )

        entries = self._list(client, employee_headers, date_from=_iso(first_day), date_to=_iso(YESTERDAY))

        lines: dict[str, list[tuple[str, str, str, int]]] = {}
        for entry in sorted(entries, key=lambda entry: entry["date"]):
            for item in entry["items"]:
                lines.setdefault(item["chain_id"], []).append(
                    (entry["date"], item["status"], item["text"], item["position"])
                )

        assert lines[long_chain] == [
            (_iso(first_day), "in_progress", "интеграция", 0),
            (_iso(TODAY - timedelta(days=3)), "blocked", "жду доступы", 1),
            (_iso(YESTERDAY), "done", "интеграция готова", 0),
        ]
        assert lines[short_chain] == [(_iso(TODAY - timedelta(days=3)), "done", "созвон", 0)]
        assert set(lines) == {long_chain, short_chain}


class TestChainsAfterBackfill:
    def test_chain_reopened_in_past_day_comes_back_to_today(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "добил", EntryItemStatus.DONE.value)])
        assert client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"] == []

        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "ещё не добил", "status": "in_progress"}]},
        )
        assert response.status_code == 200

        chains = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"]
        assert [chain["chain_id"] for chain in chains] == [chain_id]
        assert chains[0]["last_status"] == "in_progress"
        assert chains[0]["last_date"] == _iso(YESTERDAY)
        assert chains[0]["history"] == [{"date": _iso(YESTERDAY), "status": "in_progress"}]

        history = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers).json()
        assert history["last_status"] == "in_progress"

    def test_chain_closed_in_past_day_stays_open_by_later_item(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "делаю", EntryItemStatus.IN_PROGRESS.value)])
        client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "продолжаю", "status": "in_progress"}]},
        )

        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "вообще-то закрыл", "status": "done"}]},
        )
        assert response.status_code == 200

        view = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()
        assert view["open_chains"] == []
        assert [(item["chain_id"], item["status"]) for item in view["entry"]["items"]] == [(chain_id, "in_progress")]

        history = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers).json()
        assert history["last_status"] == "in_progress"
        assert history["last_date"] == _iso(TODAY)
        assert [(item["date"], item["status"]) for item in history["items"]] == [
            (_iso(YESTERDAY), "done"),
            (_iso(TODAY), "in_progress"),
        ]

        activity = client.get("/api/employee/activity", headers=employee_headers).json()
        assert activity["summary"]["open_count"] == 1

    def test_removing_first_item_shortens_chain(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        first_day = TODAY - timedelta(days=3)
        second_day = TODAY - timedelta(days=2)
        _seed_entry(db, employee_user, first_day, items=[(chain_id, "начал", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, second_day, items=[(chain_id, "продолжил", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "жду", EntryItemStatus.BLOCKED.value)])

        response = client.put(
            f"/api/employee/daily/{_iso(first_day)}",
            headers=employee_headers,
            json={"items": [{"text": "на самом деле занимался другим", "status": "done"}]},
        )
        assert response.status_code == 200
        assert all(item["chain_id"] != chain_id for item in response.json()["items"])

        chain = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"][0]
        assert chain["chain_id"] == chain_id
        assert chain["days_open"] == 3
        assert chain["title"] == "продолжил"
        assert [point["date"] for point in chain["history"]] == [_iso(second_day), _iso(YESTERDAY)]

        history = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers).json()
        assert history["first_date"] == _iso(second_day)
        assert [item["date"] for item in history["items"]] == [_iso(second_day), _iso(YESTERDAY)]

    def test_removing_only_item_drops_chain(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "единственный", EntryItemStatus.IN_PROGRESS.value)])

        response = client.put(
            f"/api/employee/daily/{_iso(YESTERDAY)}",
            headers=employee_headers,
            json={"items": [{"text": "совсем другое", "status": "done"}]},
        )
        assert response.status_code == 200

        assert client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"] == []
        assert client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers).status_code == 404
        assert client.get("/api/employee/activity", headers=employee_headers).json()["summary"]["open_count"] == 0

    def test_chain_extended_back_starts_from_new_first_day(self, client, db, employee_headers, employee_user):
        chain_id = str(uuid4())
        earlier = TODAY - timedelta(days=3)
        started = TODAY - timedelta(days=2)
        _seed_entry(db, employee_user, started, items=[(chain_id, "начал", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "продолжил", EntryItemStatus.IN_PROGRESS.value)])

        response = client.put(
            f"/api/employee/daily/{_iso(earlier)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "на самом деле начал раньше", "status": "in_progress"}]},
        )
        assert response.status_code == 200

        chain = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"][0]
        assert chain["days_open"] == 4
        assert chain["title"] == "на самом деле начал раньше"
        assert chain["last_text"] == "продолжил"
        assert [point["date"] for point in chain["history"]] == [_iso(earlier), _iso(started), _iso(YESTERDAY)]

        history = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers).json()
        assert history["first_date"] == _iso(earlier)
        assert [item["date"] for item in history["items"]] == [_iso(earlier), _iso(started), _iso(YESTERDAY)]

    def test_chain_started_today_extended_back_appears_in_open_chains(self, client, employee_headers, employee_user):
        started = client.put(
            f"/api/employee/daily/{_iso(TODAY)}",
            headers=employee_headers,
            json={"items": [{"text": "сегодня начал", "status": "in_progress"}]},
        ).json()
        chain_id = started["items"][0]["chain_id"]
        earlier = TODAY - timedelta(days=2)

        response = client.put(
            f"/api/employee/daily/{_iso(earlier)}",
            headers=employee_headers,
            json={"items": [{"chain_id": chain_id, "text": "вообще-то позавчера", "status": "in_progress"}]},
        )
        assert response.status_code == 200

        chains = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"]
        assert [chain["chain_id"] for chain in chains] == [chain_id]
        assert chains[0]["days_open"] == 3

    def test_bulk_day_off_removes_day_from_passing_chains(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        chain_id = str(uuid4())
        only_there = str(uuid4())
        first_day = TODAY - timedelta(days=3)
        middle_day = TODAY - timedelta(days=2)
        _seed_entry(db, employee_user, first_day, items=[(chain_id, "начал", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(
            db,
            employee_user,
            middle_day,
            items=[
                (chain_id, "середина", EntryItemStatus.IN_PROGRESS.value),
                (only_there, "только тут", EntryItemStatus.IN_PROGRESS.value),
            ],
        )
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "жду", EntryItemStatus.BLOCKED.value)])

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(middle_day)], "day_type": "off"},
        )
        assert response.status_code == 200

        chains = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"]
        assert [chain["chain_id"] for chain in chains] == [chain_id]
        assert chains[0]["days_open"] == 4
        assert chains[0]["last_status"] == "blocked"
        assert [point["date"] for point in chains[0]["history"]] == [_iso(first_day), _iso(YESTERDAY)]

        history = client.get(f"/api/employee/daily-chains/{chain_id}", headers=employee_headers).json()
        assert [item["date"] for item in history["items"]] == [_iso(first_day), _iso(YESTERDAY)]
        assert client.get(f"/api/employee/daily-chains/{only_there}", headers=employee_headers).status_code == 404
        assert client.get("/api/employee/activity", headers=employee_headers).json()["summary"]["open_count"] == 1

    def test_bulk_day_off_on_last_day_falls_back_to_previous_item(self, client, db, employee_headers, employee_user):
        _all_week(db, employee_user)
        chain_id = str(uuid4())
        first_day = TODAY - timedelta(days=2)
        _seed_entry(db, employee_user, first_day, items=[(chain_id, "начал", EntryItemStatus.IN_PROGRESS.value)])
        _seed_entry(db, employee_user, YESTERDAY, items=[(chain_id, "закрыл", EntryItemStatus.DONE.value)])
        assert client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"] == []

        response = client.put(
            "/api/employee/daily-bulk",
            headers=employee_headers,
            json={"dates": [_iso(YESTERDAY)], "day_type": "off"},
        )
        assert response.status_code == 200

        chains = client.get(f"/api/employee/daily/{_iso(TODAY)}", headers=employee_headers).json()["open_chains"]
        assert [chain["chain_id"] for chain in chains] == [chain_id]
        assert chains[0]["last_date"] == _iso(first_day)
        assert chains[0]["last_status"] == "in_progress"
