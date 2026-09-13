from collections import Counter
from datetime import date, timedelta

import pytest

from app.core.security import hash_password
from app.models import (
    Assessment,
    DailyEntry,
    Department,
    EmployeeProfile,
    EmployeeSettings,
    EntryItem,
    InternalChatMessage,
    Job,
    Reviewer,
    User,
)
from app.models.enums import DailyEntryStatus, DayType, OffReason, UserRole, UserStatus
from app.services.assessments import calculate_reviewer_usage
from app.services.users import access_status
from scripts.seed_demo import WORKERS, seed

TODAY = date.today()
WEEK = range(7)
PAYLOADS = {payload["name"]: payload for payload in WORKERS}
SEEDED_MODELS = [
    Assessment,
    DailyEntry,
    Department,
    EmployeeProfile,
    EmployeeSettings,
    EntryItem,
    InternalChatMessage,
    Job,
    Reviewer,
    User,
]


@pytest.fixture
def admin(db):
    user = User(
        name="Демо Админ",
        email="demo-admin@test.com",
        password_hash=hash_password("adminpass"),
        role=UserRole.ADMIN.value,
        status=UserStatus.ACTIVE.value,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _seed(db, today=TODAY):
    seed(db, today)
    db.expire_all()
    return {
        user.name: user
        for user in db.query(User).filter(User.role == UserRole.EMPLOYEE.value).all()
    }


def _entries(db, user):
    return db.query(DailyEntry).filter(DailyEntry.user_id == user.id).all()


def _assessments(db, user):
    return db.query(Assessment).filter(Assessment.worker_id == user.id).all()


def _with_status(workers, status):
    return [user for user in workers.values() if user.status == status.value]


def _counts(db):
    return {model.__tablename__: db.query(model).count() for model in SEEDED_MODELS}


def test_seed_requires_admin(db):
    with pytest.raises(SystemExit):
        seed(db, TODAY)


def test_status_follows_access_rule(db, admin):
    workers = _seed(db)

    assert set(workers) == set(PAYLOADS)
    for name, user in workers.items():
        assert user.status == access_status(user, access_open=PAYLOADS[name]["access_open"]).value
    assert {user.status for user in workers.values()} == {status.value for status in UserStatus}


def test_invited_worker_has_no_history(db, admin):
    invited = _with_status(_seed(db), UserStatus.INVITED)

    assert invited
    for user in invited:
        assert user.last_login_at is None
        assert _entries(db, user) == []
        assert _assessments(db, user) == []


def test_inactive_worker_keeps_only_history_before_last_login(db, admin):
    inactive = _with_status(_seed(db), UserStatus.INACTIVE)

    assert inactive
    for user in inactive:
        entries = _entries(db, user)
        assert entries
        assert all(entry.date <= user.last_login_at.date() for entry in entries)
        assert all(
            entry.submitted_at is None or entry.submitted_at <= user.last_login_at for entry in entries
        )
        assert all(assessment.created_at <= user.last_login_at for assessment in _assessments(db, user))


def test_worker_employed_before_first_entry_and_assessment(db, admin):
    workers = _seed(db)

    for user in workers.values():
        assert user.created_at <= user.updated_at
        entry_dates = [entry.date for entry in _entries(db, user)]
        assessments = _assessments(db, user)
        if entry_dates:
            assert user.created_at.date() <= min(entry_dates)
        if assessments:
            assert user.created_at <= min(assessment.created_at for assessment in assessments)
        assert user.created_at.date() < TODAY
        if user.last_login_at is None:
            assert (TODAY - user.created_at.date()).days <= 7


@pytest.mark.parametrize("shift", WEEK)
def test_off_entries_have_reason(db, admin, shift):
    _seed(db, TODAY - timedelta(days=shift))
    entries = db.query(DailyEntry).all()

    reasons = set()
    for entry in entries:
        if entry.day_type == DayType.WORK.value:
            assert entry.off_reason is None
            assert entry.off_reason_note is None
            continue
        reason = OffReason(entry.off_reason)
        reasons.add(reason)
        if reason is OffReason.OTHER:
            assert entry.off_reason_note
            assert len(entry.off_reason_note) <= 200
        else:
            assert entry.off_reason_note is None

    assert {OffReason.VACATION, OffReason.SICK_LEAVE, OffReason.OTHER} <= reasons


@pytest.mark.parametrize("shift", WEEK)
def test_recent_submitted_entries_are_marked_edited(db, admin, shift):
    today = TODAY - timedelta(days=shift)
    _seed(db, today)
    edited = db.query(DailyEntry).filter(DailyEntry.edited_at.isnot(None)).all()

    assert len([entry for entry in edited if entry.edited_at > entry.submitted_at]) >= 2
    assert len({entry.user_id for entry in edited}) == len(edited)
    for entry in edited:
        assert entry.status == DailyEntryStatus.SUBMITTED.value
        assert entry.day_type == DayType.WORK.value
        assert today - timedelta(days=7) <= entry.date < today
        assert entry.edited_at.date() < today


def test_assessments_follow_worker_reviewer(db, admin):
    workers = _seed(db)
    assessments = db.query(Assessment).all()

    assert assessments
    for assessment in assessments:
        worker = db.get(User, assessment.worker_id)
        job = db.get(Job, worker.job_id)
        assert assessment.reviewer_id == job.reviewer_id
        assert assessment.job_id == job.id
        assert assessment.created_by == admin.id
        assert assessment.feedback_text
        assert assessment.period_to == assessment.created_at.date()
        assert assessment.period_from == assessment.period_to - timedelta(days=29)
        assert assessment.metrics_snapshot
        assert all(metric["score"] is None for metric in assessment.metrics_snapshot)
        assert {metric["json_name"]: metric["weight"] for metric in assessment.metrics_snapshot} == {
            metric["json_name"]: metric["value"] for metric in job.reviewer.metrics
        }

    per_worker = Counter(assessment.worker_id for assessment in assessments)
    for user in workers.values():
        if user.status == UserStatus.INVITED.value:
            assert per_worker[user.id] == 0
        else:
            assert 2 <= per_worker[user.id] <= 4
    assert len({assessment.feedback_text for assessment in assessments}) == len(assessments)


def test_reviewer_usage_has_history_and_recent_assessments(db, admin):
    _seed(db)

    usages = [calculate_reviewer_usage(db, reviewer) for reviewer in db.query(Reviewer).all()]

    assert usages
    assert all(len(usage.by_month) >= 2 for usage in usages)
    assert sum(1 for usage in usages if usage.assessments_last_30_days > 0) >= 2


def test_reseed_leaves_no_duplicates_or_orphans(db, admin):
    _seed(db)
    first = _counts(db)

    workers = _seed(db)

    assert _counts(db) == first
    assert db.query(User).filter(User.role == UserRole.ADMIN.value).count() == 1
    assert len(workers) == len(PAYLOADS)
    user_ids = {user_id for (user_id,) in db.query(User.id).all()}
    reviewer_ids = {reviewer_id for (reviewer_id,) in db.query(Reviewer.id).all()}
    entry_ids = {entry_id for (entry_id,) in db.query(DailyEntry.id).all()}
    for assessment in db.query(Assessment).all():
        assert assessment.worker_id in user_ids
        assert assessment.reviewer_id in reviewer_ids
    assert all(entry.user_id in user_ids for entry in db.query(DailyEntry).all())
    assert all(item.entry_id in entry_ids for item in db.query(EntryItem).all())
