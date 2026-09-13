from datetime import date
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.dependencies import require_admin_user
from app.api.schemas.analytics import WorkerStatistics
from app.api.schemas.assessment import Assessment, AssessmentRequest
from app.api.schemas.daily_entry import WorkerDailies
from app.api.schemas.worker import Worker, WorkerAIFeedback, WorkerCreate, WorkerDetail, WorkerUpdate
from app.core.security import hash_password
from app.db.session import get_db
from app.models import DailyEntry as DailyEntryModel
from app.models import Department as DepartmentModel
from app.models import InternalChatMessage as InternalChatMessageModel
from app.models import Job as JobModel
from app.models import Statistic as StatisticModel
from app.models import User as UserModel
from app.models.enums import CLOSED_ITEM_STATUSES, EntryItemStatus, UserRole
from app.services.assessments import (
    create_assessment,
    list_worker_assessments,
    period_bounds,
    resolve_period,
    serialize_assessment,
)
from app.services.daily_entries import chain_rows, group_by_chain
from app.services.dailies_grid import build_daily_days
from app.services.gigachat import GigaChatClient
from app.services.schedule import apply_schedule_update, schedule_for_new_user
from app.services.users import ensure_employee_context, serialize_user_detail
from app.services.worker_statistics import calculate_worker_statistics, days_in_range, resolve_statistics_period


router = APIRouter(dependencies=[Depends(require_admin_user)])


def _get_worker_or_404(db: Session, worker_id: int) -> UserModel:
    user = (
        db.query(UserModel)
        .options(
            joinedload(UserModel.department),
            joinedload(UserModel.job),
            joinedload(UserModel.profile),
            joinedload(UserModel.settings),
        )
        .filter(UserModel.id == worker_id, UserModel.role == UserRole.EMPLOYEE.value)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return user


def _ensure_department(db: Session, department_id: int | None) -> None:
    if department_id is None:
        return
    if not db.get(DepartmentModel, department_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Department not found")


def _ensure_job(db: Session, job_id: int | None) -> None:
    if job_id is None:
        return
    if not db.get(JobModel, job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")


def _validate_job_department(db: Session, job_id: int | None, department_id: int | None) -> None:
    if job_id is None or department_id is None:
        return
    job = db.get(JobModel, job_id)
    if job and job.department_id != department_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job does not belong to the specified department",
        )


def _serialize_worker(user: UserModel) -> Worker:
    return Worker(
        id=user.id,
        name=user.name,
        email=user.email,
        department_id=user.department_id,
        department_name=user.department.name if user.department else None,
        job_id=user.job_id,
        job_name=user.job.name if user.job else None,
        status=user.status,
        schedule_type=user.schedule_type,
        work_days=user.work_days,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


@router.get("", response_model=List[Worker])
def list_workers(
    department_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Worker]:
    query = (
        db.query(UserModel)
        .options(joinedload(UserModel.department), joinedload(UserModel.job))
        .filter(UserModel.role == UserRole.EMPLOYEE.value)
        .order_by(UserModel.created_at.desc())
    )
    if department_id is not None:
        query = query.filter(UserModel.department_id == department_id)
    return [_serialize_worker(user) for user in query.all()]


@router.get("/{worker_id}", response_model=WorkerDetail)
def get_worker(
    worker_id: int,
    db: Session = Depends(get_db),
) -> WorkerDetail:
    user = _get_worker_or_404(db, worker_id)
    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    detail = serialize_user_detail(user)
    return WorkerDetail(**detail.model_dump())


@router.post("", response_model=WorkerDetail, status_code=status.HTTP_201_CREATED)
def create_worker(
    payload: WorkerCreate,
    db: Session = Depends(get_db),
) -> WorkerDetail:
    if payload.email:
        if db.query(UserModel).filter(UserModel.email == payload.email).first():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

    _ensure_department(db, payload.department_id)
    _ensure_job(db, payload.job_id)
    _validate_job_department(db, payload.job_id, payload.department_id)

    schedule_type, work_days = schedule_for_new_user(
        db,
        job_id=payload.job_id,
        schedule_type=payload.schedule_type,
        work_days=payload.work_days,
    )

    user = UserModel(
        name=payload.name,
        email=payload.email,
        password_hash=hash_password(payload.password) if payload.password else None,
        role=UserRole.EMPLOYEE.value,
        department_id=payload.department_id,
        job_id=payload.job_id,
        status=payload.status.value,
        schedule_type=schedule_type,
        work_days=work_days,
    )
    db.add(user)
    db.flush()
    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    detail = serialize_user_detail(user)
    return WorkerDetail(**detail.model_dump())


@router.put("/{worker_id}", response_model=WorkerDetail)
def update_worker(
    worker_id: int,
    payload: WorkerUpdate,
    db: Session = Depends(get_db),
) -> WorkerDetail:
    user = _get_worker_or_404(db, worker_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "email" in update_data and update_data["email"] is not None:
        duplicate = (
            db.query(UserModel)
            .filter(UserModel.email == update_data["email"], UserModel.id != user.id)
            .first()
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="User with this email already exists",
            )

    if "department_id" in update_data:
        _ensure_department(db, update_data["department_id"])
    if "job_id" in update_data:
        _ensure_job(db, update_data["job_id"])

    new_job_id = update_data.get("job_id", user.job_id)
    new_dept_id = update_data.get("department_id", user.department_id)
    _validate_job_department(db, new_job_id, new_dept_id)

    if "status" in update_data and update_data["status"] is not None:
        update_data["status"] = update_data["status"].value

    if "password" in update_data:
        password = update_data.pop("password")
        if password:
            user.password_hash = hash_password(password)

    apply_schedule_update(user, update_data)

    for field, value in update_data.items():
        setattr(user, field, value)

    ensure_employee_context(db, user)
    db.commit()
    db.refresh(user)
    detail = serialize_user_detail(user)
    return WorkerDetail(**detail.model_dump())


@router.post("/{worker_id}/ai-feedback", response_model=WorkerAIFeedback)
def get_worker_ai_feedback(
    worker_id: int,
    payload: AssessmentRequest | None = None,
    db: Session = Depends(get_db),
    current_admin: UserModel = Depends(require_admin_user),
) -> WorkerAIFeedback:
    user = (
        db.query(UserModel)
        .options(
            joinedload(UserModel.department),
            joinedload(UserModel.job).joinedload(JobModel.reviewer),
        )
        .filter(UserModel.id == worker_id, UserModel.role == UserRole.EMPLOYEE.value)
        .first()
    )
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    period_from, period_to = resolve_period(
        payload.date_from if payload else None,
        payload.date_to if payload else None,
    )
    since, until = period_bounds(period_from, period_to)
    period_label = f"{period_from.strftime('%d.%m.%Y')} — {period_to.strftime('%d.%m.%Y')}"

    chat_messages = (
        db.query(InternalChatMessageModel)
        .filter(
            InternalChatMessageModel.user_id == worker_id,
            InternalChatMessageModel.created_at >= since,
            InternalChatMessageModel.created_at < until,
        )
        .order_by(InternalChatMessageModel.created_at.asc())
        .limit(30)
        .all()
    )

    if not chat_messages:
        return WorkerAIFeedback(
            worker_id=worker_id,
            worker_name=user.name,
            period_from=period_from,
            period_to=period_to,
            feedback=(
                f"У сотрудника «{user.name}» нет дейликов за период {period_label}. "
                f"Оценка невозможна — недостаточно данных для анализа."
            ),
        )

    chat_text = "\n".join(
        f"[{msg.created_at.strftime('%d.%m.%Y %H:%M')}] {msg.message_text}"
        for msg in chat_messages
    )

    entries_count = (
        db.query(DailyEntryModel)
        .filter(
            DailyEntryModel.user_id == worker_id,
            DailyEntryModel.date >= period_from,
            DailyEntryModel.date <= period_to,
        )
        .count()
    )
    chains = group_by_chain(chain_rows(db, worker_id))
    statistics = (
        db.query(StatisticModel)
        .filter(
            StatisticModel.user_id == worker_id,
            StatisticModel.date >= period_from,
            StatisticModel.date <= period_to,
        )
        .order_by(StatisticModel.date.desc())
        .all()
    )

    reviewer = user.job.reviewer if user.job else None
    metrics_text = ""
    if reviewer and reviewer.metrics:
        metric_lines = [
            f"- {m.get('display_name', m.get('json_name', ''))}: {m.get('description', '')}"
            for m in reviewer.metrics
        ]
        metrics_text = f"\nКритерии оценщика «{reviewer.name}»:\n" + "\n".join(metric_lines)

    stats_text = ""
    if statistics:
        vals = ", ".join(str(s.value) for s in statistics[:10])
        stats_text = f"\nЧисловые показатели (последние {len(statistics)} дней): {vals}"

    reports_supplement = ""
    if entries_count:
        open_chains_count = sum(
            1 for rows in chains.values() if rows[-1][0].status not in CLOSED_ITEM_STATUSES
        )
        dropped_chains_count = sum(
            1 for rows in chains.values() if rows[-1][0].status == EntryItemStatus.DROPPED.value
        )
        blocked_items_count = sum(
            1
            for rows in chains.values()
            for item, day in rows
            if item.status == EntryItemStatus.BLOCKED.value and period_from <= day <= period_to
        )
        reports_supplement = (
            f"\nДополнительно — дейлики в системе ({entries_count} записей за период {period_label}):\n"
            f"Открытых линий работы: {open_chains_count}\n"
            f"Пунктов в блокере за период: {blocked_items_count}\n"
            f"Брошенных линий: {dropped_chains_count}\n"
        )

    prompt = (
        f"Ты — HR-аналитик. Дай краткую оценку сотрудника строго на основе его дейликов из внутреннего чата. "
        f"Ответ должен быть на русском языке, 3-5 предложений. Не используй markdown. "
        f"Главный и приоритетный источник данных — сообщения из внутреннего чата ниже. "
        f"Если есть формальные отчёты — учитывай их только как дополнение.\n\n"
        f"Сотрудник: {user.name}\n"
        f"Должность: {user.job.name if user.job else 'не указана'}\n"
        f"Отдел: {user.department.name if user.department else 'не указан'}\n"
        f"{metrics_text}"
        f"{stats_text}"
        f"{reports_supplement}\n"
        f"Дейлики из чата за период {period_label} ({len(chat_messages)} сообщений):\n{chat_text}"
    )

    try:
        client = GigaChatClient()
        response = client.chat(prompt)
        feedback = response["choices"][0]["message"]["content"]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"GigaChat unavailable: {exc}",
        ) from exc

    assessment = create_assessment(
        db,
        worker=user,
        job=user.job,
        reviewer=reviewer,
        created_by=current_admin.id,
        model=response.get("model") or client.model or "gigachat",
        period_from=period_from,
        period_to=period_to,
        feedback=feedback,
    )
    return WorkerAIFeedback(**serialize_assessment(assessment).model_dump())


@router.get("/{worker_id}/assessments", response_model=List[Assessment])
def list_worker_assessments_endpoint(
    worker_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> List[Assessment]:
    _get_worker_or_404(db, worker_id)
    assessments = list_worker_assessments(db, worker_id, limit=limit, offset=offset)
    return [serialize_assessment(assessment) for assessment in assessments]


@router.get("/{worker_id}/statistics", response_model=WorkerStatistics)
def get_worker_statistics(
    worker_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> WorkerStatistics:
    user = _get_worker_or_404(db, worker_id)
    period_from, period_to = resolve_statistics_period(date_from, date_to)

    entries = (
        db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(DailyEntryModel.user_id == user.id)
        .order_by(DailyEntryModel.date.asc())
        .all()
    )
    return calculate_worker_statistics(
        user,
        period_from=period_from,
        period_to=period_to,
        entries=entries,
        chain_rows=chain_rows(db, user.id),
    )


@router.get("/{worker_id}/dailies", response_model=WorkerDailies)
def get_worker_dailies(
    worker_id: int,
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    db: Session = Depends(get_db),
) -> WorkerDailies:
    user = _get_worker_or_404(db, worker_id)
    period_from, period_to = resolve_statistics_period(date_from, date_to)

    entries = (
        db.query(DailyEntryModel)
        .options(joinedload(DailyEntryModel.items))
        .filter(
            DailyEntryModel.user_id == user.id,
            DailyEntryModel.date >= period_from,
            DailyEntryModel.date <= period_to,
        )
        .all()
    )
    entries_by_date = {entry.date: entry for entry in entries}

    return WorkerDailies(
        user_id=user.id,
        user_name=user.name,
        job_name=user.job.name if user.job else None,
        department_name=user.department.name if user.department else None,
        schedule_type=user.schedule_type,
        work_days=user.work_days,
        date_from=period_from,
        date_to=period_to,
        days=build_daily_days(user, days_in_range(period_from, period_to), entries_by_date),
    )


@router.delete("/{worker_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_worker(
    worker_id: int,
    db: Session = Depends(get_db),
) -> None:
    user = _get_worker_or_404(db, worker_id)
    db.delete(user)
    db.commit()
