from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.schemas.activity import ActivityChain, ActivitySummary, EmployeeActivity
from app.api.schemas.daily_entry import ChainPoint
from app.models.enums import OPEN_ITEM_STATUSES, ActivityPeriod, ChainOutcome, EntryItemStatus
from app.services.daily_entries import ChainRows, _title, chain_rows, group_by_chain

ACTIVITY_PERIOD_DAYS: dict[ActivityPeriod, int] = {
    ActivityPeriod.WEEK: 7,
    ActivityPeriod.MONTH: 30,
}
AVG_DAYS_PRECISION = 1


def resolve_activity_period(period: ActivityPeriod, day: date | None) -> tuple[date, date]:
    today = date.today()
    date_to = day or today
    if date_to > today:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Активность за будущую дату не отдаётся",
        )
    return date_to - timedelta(days=ACTIVITY_PERIOD_DAYS[period] - 1), date_to


def chain_outcome(last_status: str) -> ChainOutcome:
    if last_status in OPEN_ITEM_STATUSES:
        return ChainOutcome.OPEN
    return ChainOutcome(last_status)


def _blocked_dates(history: list[ChainPoint], since: date | None = None) -> set[date]:
    return {
        point.date
        for point in history
        if point.status == EntryItemStatus.BLOCKED and (since is None or point.date >= since)
    }


def _activity_chain(chain_id: str, rows: ChainRows, date_from: date, date_to: date) -> ActivityChain | None:
    last_item, last_date = rows[-1]
    _, first_date = rows[0]
    outcome = chain_outcome(last_item.status)
    is_open = outcome is ChainOutcome.OPEN
    if not is_open and last_date < date_from:
        return None

    closed_date = None if is_open else last_date
    history = [ChainPoint(date=row_date, status=item.status) for item, row_date in rows]
    return ActivityChain(
        chain_id=chain_id,
        title=_title(rows),
        link=next((item.link for item, _ in reversed(rows) if item.link), None),
        first_date=first_date,
        last_date=last_date,
        last_status=last_item.status,
        outcome=outcome,
        closed_date=closed_date,
        days_total=((closed_date or date_to) - first_date).days + 1,
        blocked_days=len(_blocked_dates(history)),
        started_in_period=first_date >= date_from,
        closed_in_period=closed_date is not None,
        history=history,
    )


def _summary(chains: list[ActivityChain], date_from: date) -> ActivitySummary:
    done = [chain for chain in chains if chain.closed_in_period and chain.outcome is ChainOutcome.DONE]
    blocked_in_period = [len(_blocked_dates(chain.history, date_from)) for chain in chains]
    return ActivitySummary(
        chains_count=len(chains),
        started_count=sum(1 for chain in chains if chain.started_in_period),
        done_count=len(done),
        dropped_count=sum(
            1 for chain in chains if chain.closed_in_period and chain.outcome is ChainOutcome.DROPPED
        ),
        open_count=sum(1 for chain in chains if chain.outcome is ChainOutcome.OPEN),
        blocked_chains_count=sum(1 for days in blocked_in_period if days),
        blocked_days=sum(blocked_in_period),
        avg_days_to_done=(
            round(sum(chain.days_total for chain in done) / len(done), AVG_DAYS_PRECISION) if done else None
        ),
    )


def calculate_employee_activity(
    db: Session,
    user_id: int,
    period: ActivityPeriod,
    day: date | None,
) -> EmployeeActivity:
    date_from, date_to = resolve_activity_period(period, day)
    grouped = group_by_chain(chain_rows(db, user_id, before=date_to + timedelta(days=1)))

    chains = [
        chain
        for chain_id, rows in grouped.items()
        if (chain := _activity_chain(chain_id, rows, date_from, date_to)) is not None
    ]
    chains.sort(key=lambda chain: (chain.first_date, chain.chain_id))

    return EmployeeActivity(
        period=period,
        date_from=date_from,
        date_to=date_to,
        summary=_summary(chains, date_from),
        chains=chains,
    )
