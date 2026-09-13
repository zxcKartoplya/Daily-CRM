from datetime import date, datetime, timedelta

import pytest

from app.models import Assessment, Department, InternalChatMessage, Job, Reviewer, User
from app.models.enums import UserRole, UserStatus

TODAY = date.today()


def _reviewer(db, metrics=None):
    reviewer = Reviewer(
        name="Тимлид",
        description="Оценщик разработчиков",
        metrics=metrics
        if metrics is not None
        else [
            {
                "value": 30,
                "json_name": "delivery",
                "display_name": "Соблюдение сроков",
                "description": "Как держит сроки",
            },
            {
                "value": 20,
                "json_name": "quality",
                "display_name": "Качество",
                "description": "Качество результата",
            },
        ],
    )
    db.add(reviewer)
    db.commit()
    db.refresh(reviewer)
    return reviewer


def _job(db, reviewer, name="Разработчик"):
    department = db.query(Department).filter(Department.name == "Разработка").first()
    if not department:
        department = Department(name="Разработка")
        db.add(department)
        db.commit()
        db.refresh(department)
    job = Job(name=name, department_id=department.id, reviewer_id=reviewer.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def _worker(db, name="Иванов Иван", job=None, status=UserStatus.ACTIVE.value):
    user = User(
        name=name,
        email=f"{name.replace(' ', '.').lower()}@test.com",
        role=UserRole.EMPLOYEE.value,
        status=status,
        job_id=job.id if job else None,
        department_id=job.department_id if job else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _chat_message(db, worker, when, text="Сделал задачу"):
    message = InternalChatMessage(user_id=worker.id, message_text=text, created_at=when)
    db.add(message)
    db.commit()
    return message


def _stored_assessment(db, worker, reviewer, created_at, metrics_snapshot=None):
    assessment = Assessment(
        worker_id=worker.id,
        reviewer_id=reviewer.id if reviewer else None,
        job_id=worker.job_id,
        created_at=created_at,
        created_by=None,
        model="gigachat",
        period_from=created_at.date() - timedelta(days=29),
        period_to=created_at.date(),
        feedback_text="Текст оценки",
        metrics_snapshot=metrics_snapshot if metrics_snapshot is not None else [],
    )
    db.add(assessment)
    db.commit()
    db.refresh(assessment)
    return assessment


@pytest.fixture
def gigachat_stub(monkeypatch):
    calls = []

    class StubClient:
        model = "GigaChat"

        def __init__(self, *args, **kwargs):
            pass

        def chat(self, prompt):
            calls.append(prompt)
            return {
                "model": "GigaChat:1.0.26.20",
                "choices": [{"message": {"content": "Сотрудник стабильно закрывает задачи."}}],
            }

    monkeypatch.setattr("app.api.routes.admin_workers.GigaChatClient", StubClient)
    return calls


class TestAIFeedbackAssessment:
    def test_feedback_is_stored_with_metrics_snapshot(
        self, client, admin_headers, admin_user, db, gigachat_stub
    ):
        reviewer = _reviewer(db)
        job = _job(db, reviewer)
        worker = _worker(db, job=job)
        _chat_message(db, worker, datetime.utcnow() - timedelta(days=1))

        response = client.post(
            f"/api/admin/workers/{worker.id}/ai-feedback", headers=admin_headers
        )
        assert response.status_code == 200
        body = response.json()

        assert body["id"] is not None
        assert body["worker_id"] == worker.id
        assert body["worker_name"] == worker.name
        assert body["reviewer_id"] == reviewer.id
        assert body["reviewer_name"] == reviewer.name
        assert body["job_id"] == job.id
        assert body["created_by"] == admin_user.id
        assert body["model"] == "GigaChat:1.0.26.20"
        assert body["feedback"] == "Сотрудник стабильно закрывает задачи."
        assert body["period_to"] == TODAY.isoformat()
        assert body["period_from"] == (TODAY - timedelta(days=29)).isoformat()
        assert body["metrics_snapshot"] == [
            {
                "json_name": "delivery",
                "display_name": "Соблюдение сроков",
                "weight": 30,
                "score": None,
            },
            {
                "json_name": "quality",
                "display_name": "Качество",
                "weight": 20,
                "score": None,
            },
        ]
        assert db.query(Assessment).count() == 1

    def test_custom_period_limits_messages_and_is_stored(
        self, client, admin_headers, db, gigachat_stub
    ):
        reviewer = _reviewer(db)
        worker = _worker(db, job=_job(db, reviewer))
        _chat_message(db, worker, datetime.utcnow() - timedelta(days=100), text="Старое")

        date_from = (TODAY - timedelta(days=120)).isoformat()
        date_to = (TODAY - timedelta(days=90)).isoformat()
        response = client.post(
            f"/api/admin/workers/{worker.id}/ai-feedback",
            headers=admin_headers,
            json={"date_from": date_from, "date_to": date_to},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["period_from"] == date_from
        assert body["period_to"] == date_to
        assert "Старое" in gigachat_stub[0]

    def test_worker_without_reviewer_is_stored_without_metrics(
        self, client, admin_headers, db, gigachat_stub
    ):
        worker = _worker(db, name="Без должности")
        _chat_message(db, worker, datetime.utcnow())

        body = client.post(
            f"/api/admin/workers/{worker.id}/ai-feedback", headers=admin_headers
        ).json()
        assert body["reviewer_id"] is None
        assert body["job_id"] is None
        assert body["metrics_snapshot"] == []
        assert db.query(Assessment).count() == 1

    def test_no_dailies_does_not_create_record(self, client, admin_headers, db, gigachat_stub):
        worker = _worker(db, job=_job(db, _reviewer(db)))

        response = client.post(
            f"/api/admin/workers/{worker.id}/ai-feedback", headers=admin_headers
        )
        assert response.status_code == 200
        body = response.json()
        assert body["id"] is None
        assert body["created_at"] is None
        assert "Оценка невозможна" in body["feedback"]
        assert gigachat_stub == []
        assert db.query(Assessment).count() == 0

    def test_inverted_period_is_rejected(self, client, admin_headers, db, gigachat_stub):
        worker = _worker(db, job=_job(db, _reviewer(db)))

        response = client.post(
            f"/api/admin/workers/{worker.id}/ai-feedback",
            headers=admin_headers,
            json={"date_from": TODAY.isoformat(), "date_to": (TODAY - timedelta(days=1)).isoformat()},
        )
        assert response.status_code == 422

    def test_requires_admin(self, client, employee_headers, db, gigachat_stub):
        worker = _worker(db)
        response = client.post(
            f"/api/admin/workers/{worker.id}/ai-feedback", headers=employee_headers
        )
        assert response.status_code == 403


class TestWorkerAssessmentsList:
    def test_sorted_from_new_to_old(self, client, admin_headers, db):
        reviewer = _reviewer(db)
        worker = _worker(db, job=_job(db, reviewer))
        older = _stored_assessment(db, worker, reviewer, datetime(2026, 7, 1, 10, 0))
        newer = _stored_assessment(db, worker, reviewer, datetime(2026, 8, 1, 10, 0))

        body = client.get(
            f"/api/admin/workers/{worker.id}/assessments", headers=admin_headers
        ).json()
        assert [item["id"] for item in body] == [newer.id, older.id]
        assert body[0]["worker_name"] == worker.name
        assert body[0]["reviewer_name"] == reviewer.name
        assert body[0]["feedback"] == "Текст оценки"

    def test_limit_and_offset(self, client, admin_headers, db):
        reviewer = _reviewer(db)
        worker = _worker(db, job=_job(db, reviewer))
        first = _stored_assessment(db, worker, reviewer, datetime(2026, 7, 1, 10, 0))
        second = _stored_assessment(db, worker, reviewer, datetime(2026, 8, 1, 10, 0))

        body = client.get(
            f"/api/admin/workers/{worker.id}/assessments",
            headers=admin_headers,
            params={"limit": 1, "offset": 1},
        ).json()
        assert [item["id"] for item in body] == [first.id]
        assert second.id not in [item["id"] for item in body]

    def test_empty_history_returns_empty_list(self, client, admin_headers, db):
        worker = _worker(db)
        response = client.get(
            f"/api/admin/workers/{worker.id}/assessments", headers=admin_headers
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_unknown_worker_returns_404(self, client, admin_headers):
        assert client.get("/api/admin/workers/999/assessments", headers=admin_headers).status_code == 404


class TestAssessmentById:
    def test_returns_single_assessment(self, client, admin_headers, db):
        reviewer = _reviewer(db)
        worker = _worker(db, job=_job(db, reviewer))
        assessment = _stored_assessment(db, worker, reviewer, datetime(2026, 8, 1, 10, 0))

        body = client.get(f"/api/admin/assessments/{assessment.id}", headers=admin_headers).json()
        assert body["id"] == assessment.id
        assert body["worker_id"] == worker.id
        assert body["period_from"] == assessment.period_from.isoformat()

    def test_unknown_assessment_returns_404(self, client, admin_headers):
        assert client.get("/api/admin/assessments/999", headers=admin_headers).status_code == 404

    def test_requires_admin(self, client, employee_headers):
        assert client.get("/api/admin/assessments/1", headers=employee_headers).status_code == 403


class TestReviewerUsage:
    def test_usage_aggregates(self, client, admin_headers, db):
        reviewer = _reviewer(db)
        job = _job(db, reviewer)
        worker = _worker(db, job=job)
        other = _worker(db, name="Петров Пётр", job=job)
        _worker(db, name="Уволенный", job=job, status=UserStatus.INACTIVE.value)

        _stored_assessment(db, worker, reviewer, datetime(2026, 7, 10, 10, 0))
        _stored_assessment(db, worker, reviewer, datetime(2026, 7, 20, 10, 0))
        recent = _stored_assessment(db, other, reviewer, datetime.utcnow() - timedelta(days=2))

        body = client.get(f"/api/admin/reviewers/{reviewer.id}/usage", headers=admin_headers).json()
        assert body["reviewer_id"] == reviewer.id
        assert body["assessments_count"] == 3
        assert body["assessments_last_30_days"] == 1
        assert body["last_assessment_at"].startswith(recent.created_at.isoformat()[:19])
        assert body["workers_evaluated"] == 2
        assert body["jobs_count"] == 1
        assert body["employees_covered"] == 2
        assert {"month": "2026-07", "count": 2} in body["by_month"]
        assert body["by_month"] == sorted(body["by_month"], key=lambda item: item["month"])
        assert body["avg_scores"] == []

    def test_usage_without_assessments(self, client, admin_headers, db):
        reviewer = _reviewer(db)
        body = client.get(f"/api/admin/reviewers/{reviewer.id}/usage", headers=admin_headers).json()
        assert body["assessments_count"] == 0
        assert body["last_assessment_at"] is None
        assert body["by_month"] == []
        assert body["avg_scores"] == []
        assert body["jobs_count"] == 0
        assert body["employees_covered"] == 0

    def test_avg_scores_use_stored_numeric_scores(self, client, admin_headers, db):
        reviewer = _reviewer(db)
        worker = _worker(db, job=_job(db, reviewer))
        snapshot = [
            {"json_name": "delivery", "display_name": "Соблюдение сроков", "weight": 30, "score": 4.0},
            {"json_name": "quality", "display_name": "Качество", "weight": 20, "score": None},
        ]
        _stored_assessment(db, worker, reviewer, datetime(2026, 7, 10, 10, 0), snapshot)
        second = [dict(snapshot[0], score=5.0), snapshot[1]]
        _stored_assessment(db, worker, reviewer, datetime(2026, 7, 11, 10, 0), second)

        body = client.get(f"/api/admin/reviewers/{reviewer.id}/usage", headers=admin_headers).json()
        assert body["avg_scores"] == [
            {
                "json_name": "delivery",
                "display_name": "Соблюдение сроков",
                "avg_score": 4.5,
                "samples": 2,
            }
        ]

    def test_unknown_reviewer_returns_404(self, client, admin_headers):
        assert client.get("/api/admin/reviewers/999/usage", headers=admin_headers).status_code == 404
