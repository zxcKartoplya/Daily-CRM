from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.api.schemas.daily_entry import (
    BulkDayTypeWrite,
    ChainHistory,
    ChainItem,
    ChainPoint,
    DailyEntryWrite,
    DayView,
    EntryItemInput,
    OpenChain,
)
from app.core.config import get_settings
from app.models import DailyEntry as DailyEntryModel
from app.models import EntryItem as EntryItemModel
from app.models import User as UserModel
from app.models.enums import OPEN_ITEM_STATUSES, DailyEntryStatus, DayType
from app.services.schedule import working_days_in_range

ChainRows = list[tuple[EntryItemModel, date]]


def backfill_window_days() -> int:
    return get_settings().daily_backfill_window_days


def earliest_editable_date(today: date) -> date:
    return today - timedelta(days=backfill_window_days())


def get_entry(db: Session, user_id: int, day: date) -> DailyEntryModel | None:
    return (
        db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(DailyEntryModel.user_id == user_id, DailyEntryModel.date == day)
        .first()
    )


def list_entries(
    db: Session,
    user_id: int,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[DailyEntryModel]:
    query = (
        db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(DailyEntryModel.user_id == user_id)
        .order_by(DailyEntryModel.date.desc())
    )
    if date_from is not None:
        query = query.filter(DailyEntryModel.date >= date_from)
    if date_to is not None:
        query = query.filter(DailyEntryModel.date <= date_to)
    return query.all()


def _ensure_writable(entry: DailyEntryModel | None, day: date) -> None:
    today = date.today()
    if day > today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дейлик за будущую дату не заполняется",
        )

    window = backfill_window_days()
    if day < earliest_editable_date(today):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Заполнить задним числом можно в пределах {window} дней",
        )

    if entry is not None and entry.status == DailyEntryStatus.SUBMITTED.value and day < today:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Отправленная запись прошлого дня закрыта на изменения",
        )


def _ordered_items(items: list[EntryItemInput]) -> list[tuple[int, EntryItemInput]]:
    by_position = sorted(
        enumerate(items),
        key=lambda pair: (pair[0] if pair[1].position is None else pair[1].position, pair[0]),
    )
    return [(position, item) for position, (_, item) in enumerate(by_position)]


def _ensure_known_chains(db: Session, user_id: int, chain_ids: set[str]) -> None:
    if not chain_ids:
        return

    known = {
        row[0]
        for row in db.query(EntryItemModel.chain_id)
        .join(DailyEntryModel, EntryItemModel.entry_id == DailyEntryModel.id)
        .filter(DailyEntryModel.user_id == user_id, EntryItemModel.chain_id.in_(chain_ids))
        .distinct()
        .all()
    }
    unknown = chain_ids - known
    if unknown:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Линия работы не найдена: {', '.join(sorted(unknown))}",
        )


def _validate_items(db: Session, user_id: int, ordered: list[tuple[int, EntryItemInput]]) -> None:
    seen: set[str] = set()
    for _, item in ordered:
        if item.chain_id is None:
            continue
        chain_id = str(item.chain_id)
        if chain_id in seen:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="По одной линии работы допустим только один пункт в день",
            )
        seen.add(chain_id)

    _ensure_known_chains(db, user_id, seen)


def _replace_items(db: Session, entry: DailyEntryModel, ordered: list[tuple[int, EntryItemInput]]) -> None:
    existing = {item.chain_id: item for item in entry.items}
    kept: set[str] = set()

    for position, payload_item in ordered:
        chain_id = str(payload_item.chain_id) if payload_item.chain_id is not None else str(uuid4())
        kept.add(chain_id)

        item = existing.get(chain_id)
        if item is None:
            item = EntryItemModel(chain_id=chain_id)
            entry.items.append(item)

        item.text = payload_item.text
        item.status = payload_item.status.value
        item.link = payload_item.link
        item.position = position

    for chain_id, item in existing.items():
        if chain_id not in kept:
            entry.items.remove(item)
            db.delete(item)


def upsert_entry(db: Session, user: UserModel, day: date, payload: DailyEntryWrite) -> DailyEntryModel:
    entry = get_entry(db, user.id, day)
    _ensure_writable(entry, day)

    if payload.day_type is DayType.OFF and payload.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У нерабочего дня не может быть пунктов",
        )

    ordered = _ordered_items(payload.items)
    _validate_items(db, user.id, ordered)

    if entry is None:
        entry = DailyEntryModel(
            user_id=user.id,
            department_id=user.department_id,
            date=day,
            day_type=payload.day_type.value,
            status=DailyEntryStatus.DRAFT.value,
        )
        db.add(entry)
        db.flush()
    else:
        entry.day_type = payload.day_type.value

    _replace_items(db, entry, ordered)
    db.flush()
    return entry


def submit_entry(db: Session, user: UserModel, day: date) -> DailyEntryModel:
    entry = get_entry(db, user.id, day)
    if entry is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись за эту дату не найдена")

    _ensure_writable(entry, day)

    if entry.status == DailyEntryStatus.SUBMITTED.value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Запись уже отправлена")

    if entry.day_type == DayType.WORK.value and not entry.items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Нельзя отправить рабочий день без пунктов",
        )

    entry.status = DailyEntryStatus.SUBMITTED.value
    entry.submitted_at = datetime.utcnow()
    db.flush()
    return entry


def bulk_set_day_type(db: Session, user: UserModel, payload: BulkDayTypeWrite) -> list[DailyEntryModel]:
    if payload.day_type is not DayType.OFF:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Массово проставляется только нерабочий день",
        )

    days = sorted(set(payload.dates))
    if not days:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Список дат пуст")

    existing = {
        entry.date: entry
        for entry in db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(DailyEntryModel.user_id == user.id, DailyEntryModel.date.in_(days))
        .all()
    }

    for day in days:
        _ensure_writable(existing.get(day), day)

    entries: list[DailyEntryModel] = []
    for day in days:
        entry = existing.get(day)
        if entry is None:
            entry = DailyEntryModel(
                user_id=user.id,
                department_id=user.department_id,
                date=day,
            )
            db.add(entry)
            db.flush()
        else:
            _replace_items(db, entry, [])

        entry.day_type = DayType.OFF.value
        entry.status = DailyEntryStatus.SUBMITTED.value
        entry.submitted_at = datetime.utcnow()
        entries.append(entry)

    db.flush()
    return entries


def chain_rows(
    db: Session,
    user_id: int,
    *,
    before: date | None = None,
    chain_id: str | None = None,
) -> ChainRows:
    query = (
        db.query(EntryItemModel, DailyEntryModel.date)
        .join(DailyEntryModel, EntryItemModel.entry_id == DailyEntryModel.id)
        .filter(DailyEntryModel.user_id == user_id)
    )
    if before is not None:
        query = query.filter(DailyEntryModel.date < before)
    if chain_id is not None:
        query = query.filter(EntryItemModel.chain_id == chain_id)
    return query.order_by(DailyEntryModel.date.asc(), EntryItemModel.position.asc()).all()


def chain_summaries(db: Session, *, department_id: int | None = None) -> list[tuple[int, int | None, str, str]]:
    """Последний статус каждой линии: (user_id, department_id, chain_id, last_status)."""
    query = db.query(
        DailyEntryModel.user_id,
        DailyEntryModel.department_id,
        DailyEntryModel.date,
        EntryItemModel.chain_id,
        EntryItemModel.status,
        EntryItemModel.position,
    ).join(EntryItemModel, EntryItemModel.entry_id == DailyEntryModel.id)
    if department_id is not None:
        query = query.filter(DailyEntryModel.department_id == department_id)

    latest: dict[tuple[int, str], tuple[date, int, int | None, str]] = {}
    for user_id, dept_id, day, chain_id, item_status, position in query.all():
        key = (user_id, chain_id)
        current = latest.get(key)
        if current is None or (day, position) >= (current[0], current[1]):
            latest[key] = (day, position, dept_id, item_status)

    return [
        (user_id, dept_id, chain_id, last_status)
        for (user_id, chain_id), (_, _, dept_id, last_status) in latest.items()
    ]


def group_by_chain(rows: ChainRows) -> dict[str, ChainRows]:
    chains: dict[str, ChainRows] = {}
    for item, day in rows:
        chains.setdefault(item.chain_id, []).append((item, day))
    return chains


def _title(rows: ChainRows) -> str | None:
    return next((item.text for item, _ in rows if item.text and item.text.strip()), None)


def open_chains(db: Session, user_id: int, day: date) -> list[OpenChain]:
    chains = group_by_chain(chain_rows(db, user_id, before=day))

    result: list[OpenChain] = []
    for chain_id, rows in chains.items():
        last_item, last_date = rows[-1]
        if last_item.status not in OPEN_ITEM_STATUSES:
            continue

        _, first_date = rows[0]
        result.append(
            OpenChain(
                chain_id=chain_id,
                title=_title(rows),
                last_status=last_item.status,
                last_text=last_item.text,
                last_date=last_date,
                days_open=(day - first_date).days + 1,
                link=next((item.link for item, _ in reversed(rows) if item.link), None),
                history=[ChainPoint(date=row_date, status=item.status) for item, row_date in rows],
            )
        )

    result.sort(key=lambda chain: (chain.last_date, chain.chain_id))
    return result


def missing_days(db: Session, user: UserModel, day: date) -> list[date]:
    today = date.today()
    window_start = earliest_editable_date(today)
    window_end = min(day, today) - timedelta(days=1)
    if window_start > window_end:
        return []

    candidates = working_days_in_range(user, window_start, window_end)
    if not candidates:
        return []

    filled = {
        row[0]
        for row in db.query(DailyEntryModel.date)
        .filter(
            DailyEntryModel.user_id == user.id,
            DailyEntryModel.date >= window_start,
            DailyEntryModel.date <= window_end,
        )
        .all()
    }
    return [candidate for candidate in candidates if candidate not in filled]


def day_view(db: Session, user: UserModel, day: date) -> DayView:
    return DayView(
        entry=get_entry(db, user.id, day),
        open_chains=open_chains(db, user.id, day),
        missing_days=missing_days(db, user, day),
        editable_from=earliest_editable_date(date.today()),
    )


def chain_history(db: Session, user_id: int, chain_id: str) -> ChainHistory:
    rows = chain_rows(db, user_id, chain_id=chain_id)
    if not rows:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Линия работы не найдена")

    last_item, last_date = rows[-1]
    _, first_date = rows[0]
    return ChainHistory(
        chain_id=chain_id,
        title=_title(rows),
        last_status=last_item.status,
        first_date=first_date,
        last_date=last_date,
        items=[
            ChainItem(
                id=item.id,
                entry_id=item.entry_id,
                date=day,
                text=item.text,
                status=item.status,
                link=item.link,
                position=item.position,
            )
            for item, day in rows
        ],
    )
