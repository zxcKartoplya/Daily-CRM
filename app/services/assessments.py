from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, List, Mapping, Sequence

from sqlalchemy.orm import Session, joinedload

from app.api.schemas.assessment import Assessment as AssessmentSchema
from app.api.schemas.reviewer import ReviewerUsage, ReviewerUsageMetric, ReviewerUsageMonth
from app.models import Assessment as AssessmentModel
from app.models import Job as JobModel
from app.models import Reviewer as ReviewerModel
from app.models import User as UserModel
from app.models.enums import UserRole
from app.services.day_state import is_tracked_employee

DEFAULT_PERIOD_DAYS = 30
USAGE_WINDOW_DAYS = 30
SCORE_MIN = 1
SCORE_MAX = 10


@dataclass(frozen=True)
class ParsedFeedback:
    feedback: str
    scores: dict[str, float]


def resolve_period(date_from: date | None, date_to: date | None) -> tuple[date, date]:
    period_to = date_to or date.today()
    period_from = date_from or period_to - timedelta(days=DEFAULT_PERIOD_DAYS - 1)
    return period_from, period_to


def period_bounds(period_from: date, period_to: date) -> tuple[datetime, datetime]:
    return (
        datetime.combine(period_from, datetime.min.time()),
        datetime.combine(period_to + timedelta(days=1), datetime.min.time()),
    )


def reviewer_metric_names(reviewer: ReviewerModel | None) -> List[str]:
    if reviewer is None or not reviewer.metrics:
        return []
    names: List[str] = []
    for metric in reviewer.metrics:
        json_name = metric.get("json_name")
        if json_name and json_name not in names:
            names.append(json_name)
    return names


def feedback_response_instruction(metric_names: Sequence[str]) -> str:
    if not metric_names:
        return "Ответ должен быть на русском языке, 3-5 предложений. Не используй markdown. "
    return (
        "Ответ верни строго в JSON без markdown и без пояснений. "
        "Структура: {\"feedback\": string, \"scores\": {\"<json_name>\": number}}. "
        "В поле feedback — оценка сотрудника на русском языке, 3-5 предложений, без markdown. "
        f"В поле scores — балл сотрудника от {SCORE_MIN} до {SCORE_MAX} по каждому критерию оценщика, "
        f"где {SCORE_MIN} — худший результат, {SCORE_MAX} — лучший. "
        "Ключ — json_name критерия, значение — число. "
        "Балл оценивает самого сотрудника по критерию и не связан с приоритетом критерия. "
        f"Ключи scores: {', '.join(metric_names)}. "
    )


def _strip_code_fence(content: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)


def _valid_score(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    return SCORE_MIN <= value <= SCORE_MAX


def parse_feedback_response(content: str, metric_names: Sequence[str]) -> ParsedFeedback:
    if not metric_names:
        return ParsedFeedback(feedback=content, scores={})

    cleaned = _strip_code_fence(content)
    try:
        data = json.loads(cleaned)
    except ValueError:
        return ParsedFeedback(feedback=cleaned, scores={})

    feedback = data.get("feedback") if isinstance(data, dict) else None
    if not isinstance(feedback, str) or not feedback.strip():
        return ParsedFeedback(feedback=cleaned, scores={})

    raw_scores = data.get("scores")
    if not isinstance(raw_scores, dict):
        raw_scores = {}
    scores = {
        name: raw_scores[name]
        for name in metric_names
        if name in raw_scores and _valid_score(raw_scores[name])
    }
    return ParsedFeedback(feedback=feedback.strip(), scores=scores)


def metrics_snapshot(
    reviewer: ReviewerModel | None,
    scores: Mapping[str, float] | None = None,
) -> List[dict[str, Any]]:
    if reviewer is None or not reviewer.metrics:
        return []
    scores = scores or {}
    snapshot = []
    for metric in reviewer.metrics:
        json_name = metric.get("json_name")
        if not json_name:
            continue
        snapshot.append(
            {
                "json_name": json_name,
                "display_name": metric.get("display_name") or json_name,
                "weight": metric.get("value"),
                "score": scores.get(json_name),
            }
        )
    return snapshot


def create_assessment(
    db: Session,
    *,
    worker: UserModel,
    job: JobModel | None,
    reviewer: ReviewerModel | None,
    created_by: int | None,
    model: str,
    period_from: date,
    period_to: date,
    feedback: str,
    scores: Mapping[str, float] | None = None,
) -> AssessmentModel:
    assessment = AssessmentModel(
        worker_id=worker.id,
        reviewer_id=reviewer.id if reviewer else None,
        job_id=job.id if job else None,
        created_by=created_by,
        model=model,
        period_from=period_from,
        period_to=period_to,
        feedback_text=feedback,
        metrics_snapshot=metrics_snapshot(reviewer, scores),
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


def serialize_assessment(assessment: AssessmentModel) -> AssessmentSchema:
    return AssessmentSchema(
        id=assessment.id,
        worker_id=assessment.worker_id,
        worker_name=assessment.worker.name if assessment.worker else "",
        reviewer_id=assessment.reviewer_id,
        reviewer_name=assessment.reviewer.name if assessment.reviewer else None,
        job_id=assessment.job_id,
        job_name=assessment.job.name if assessment.job else None,
        created_at=assessment.created_at,
        created_by=assessment.created_by,
        model=assessment.model,
        period_from=assessment.period_from,
        period_to=assessment.period_to,
        feedback=assessment.feedback_text,
        metrics_snapshot=assessment.metrics_snapshot or [],
    )


def _assessments_query(db: Session):
    return db.query(AssessmentModel).options(
        joinedload(AssessmentModel.worker),
        joinedload(AssessmentModel.reviewer),
        joinedload(AssessmentModel.job),
    )


def get_assessment(db: Session, assessment_id: int) -> AssessmentModel | None:
    return _assessments_query(db).filter(AssessmentModel.id == assessment_id).first()


def list_worker_assessments(
    db: Session,
    worker_id: int,
    *,
    limit: int,
    offset: int,
) -> List[AssessmentModel]:
    return (
        _assessments_query(db)
        .filter(AssessmentModel.worker_id == worker_id)
        .order_by(AssessmentModel.created_at.desc(), AssessmentModel.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def _by_month(assessments: Sequence[AssessmentModel]) -> List[ReviewerUsageMonth]:
    counts: dict[str, int] = defaultdict(int)
    for assessment in assessments:
        counts[assessment.created_at.strftime("%Y-%m")] += 1
    return [ReviewerUsageMonth(month=month, count=counts[month]) for month in sorted(counts)]


def _avg_scores(assessments: Sequence[AssessmentModel]) -> List[ReviewerUsageMetric]:
    totals: dict[str, float] = defaultdict(float)
    samples: dict[str, int] = defaultdict(int)
    display_names: dict[str, str] = {}
    for assessment in sorted(assessments, key=lambda item: item.created_at):
        for metric in assessment.metrics_snapshot or []:
            json_name = metric.get("json_name")
            score = metric.get("score")
            if not json_name:
                continue
            display_names[json_name] = metric.get("display_name") or json_name
            if score is None:
                continue
            totals[json_name] += float(score)
            samples[json_name] += 1
    return [
        ReviewerUsageMetric(
            json_name=json_name,
            display_name=display_names[json_name],
            avg_score=round(totals[json_name] / samples[json_name], 2),
            samples=samples[json_name],
        )
        for json_name in sorted(samples)
    ]


def calculate_reviewer_usage(db: Session, reviewer: ReviewerModel) -> ReviewerUsage:
    assessments = (
        db.query(AssessmentModel)
        .filter(AssessmentModel.reviewer_id == reviewer.id)
        .order_by(AssessmentModel.created_at.desc())
        .all()
    )

    window_start = datetime.utcnow() - timedelta(days=USAGE_WINDOW_DAYS)
    job_ids = [job.id for job in reviewer.jobs]

    employees_covered = 0
    if job_ids:
        employees_covered = sum(
            1
            for user in db.query(UserModel)
            .filter(UserModel.job_id.in_(job_ids), UserModel.role == UserRole.EMPLOYEE.value)
            .all()
            if is_tracked_employee(user)
        )

    return ReviewerUsage(
        reviewer_id=reviewer.id,
        assessments_count=len(assessments),
        assessments_last_30_days=sum(
            1 for assessment in assessments if assessment.created_at >= window_start
        ),
        last_assessment_at=assessments[0].created_at if assessments else None,
        workers_evaluated=len({assessment.worker_id for assessment in assessments}),
        jobs_count=len(job_ids),
        employees_covered=employees_covered,
        by_month=_by_month(assessments),
        avg_scores=_avg_scores(assessments),
        score_max=SCORE_MAX,
    )
