from app.models import Department, Job, Reviewer


def _job(db, **overrides):
    department = Department(name=overrides.pop("department_name", "Разработка"))
    reviewer = Reviewer(name="Тимлид", description="Ревью разработки")
    db.add_all([department, reviewer])
    db.flush()

    job = Job(
        name=overrides.pop("name", "Программист"),
        department_id=department.id,
        reviewer_id=reviewer.id,
        schedule_type=overrides.pop("schedule_type", "weekly"),
        work_days=overrides.pop("work_days", [1, 2, 3, 4, 5]),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    db.refresh(department)
    return job, department


class TestJobSchedule:
    def test_job_defaults_to_five_two(self, client, admin_headers, db):
        _, department = _job(db)
        reviewer_id = db.query(Reviewer).first().id

        response = client.post(
            "/api/admin/jobs",
            headers=admin_headers,
            json={"name": "Дизайнер", "department_id": department.id, "reviewer_id": reviewer_id},
        )
        assert response.status_code == 201
        assert response.json()["schedule_type"] == "weekly"
        assert response.json()["work_days"] == [1, 2, 3, 4, 5]

    def test_job_schedule_none_drops_work_days(self, client, admin_headers, db):
        _, department = _job(db)
        reviewer_id = db.query(Reviewer).first().id

        response = client.post(
            "/api/admin/jobs",
            headers=admin_headers,
            json={
                "name": "Оператор",
                "department_id": department.id,
                "reviewer_id": reviewer_id,
                "schedule_type": "none",
                "work_days": [1, 2],
            },
        )
        assert response.status_code == 201
        assert response.json()["schedule_type"] == "none"
        assert response.json()["work_days"] is None

    def test_weekly_without_work_days_rejected(self, client, admin_headers, db):
        _, department = _job(db)
        reviewer_id = db.query(Reviewer).first().id

        response = client.post(
            "/api/admin/jobs",
            headers=admin_headers,
            json={
                "name": "Аналитик",
                "department_id": department.id,
                "reviewer_id": reviewer_id,
                "schedule_type": "weekly",
                "work_days": [],
            },
        )
        assert response.status_code == 400

    def test_invalid_weekday_rejected(self, client, admin_headers, db):
        _, department = _job(db)
        reviewer_id = db.query(Reviewer).first().id

        response = client.post(
            "/api/admin/jobs",
            headers=admin_headers,
            json={
                "name": "Тестировщик",
                "department_id": department.id,
                "reviewer_id": reviewer_id,
                "work_days": [0, 9],
            },
        )
        assert response.status_code == 400


class TestWorkerSchedule:
    def test_worker_inherits_schedule_from_job(self, client, admin_headers, db):
        job, department = _job(db, work_days=[1, 2, 3, 4, 5, 6])

        response = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={
                "name": "Новый работник",
                "email": "worker@test.com",
                "department_id": department.id,
                "job_id": job.id,
            },
        )
        assert response.status_code == 201
        assert response.json()["schedule_type"] == "weekly"
        assert response.json()["work_days"] == [1, 2, 3, 4, 5, 6]

    def test_worker_inherits_schedule_none(self, client, admin_headers, db):
        job, department = _job(db, schedule_type="none", work_days=None)

        response = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={
                "name": "Почасовой",
                "email": "hourly@test.com",
                "department_id": department.id,
                "job_id": job.id,
            },
        )
        assert response.status_code == 201
        assert response.json()["schedule_type"] == "none"
        assert response.json()["work_days"] is None

    def test_explicit_schedule_overrides_job(self, client, admin_headers, db):
        job, department = _job(db)

        response = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={
                "name": "Особый график",
                "email": "special@test.com",
                "department_id": department.id,
                "job_id": job.id,
                "work_days": [2, 4],
            },
        )
        assert response.status_code == 201
        assert response.json()["work_days"] == [2, 4]

    def test_worker_without_job_gets_default(self, client, admin_headers):
        response = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={"name": "Без профессии", "email": "nojob@test.com"},
        )
        assert response.status_code == 201
        assert response.json()["work_days"] == [1, 2, 3, 4, 5]

    def test_worker_schedule_is_editable(self, client, admin_headers, db):
        job, department = _job(db)
        worker_id = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={
                "name": "Правим график",
                "email": "editable@test.com",
                "department_id": department.id,
                "job_id": job.id,
            },
        ).json()["id"]

        response = client.put(
            f"/api/admin/workers/{worker_id}",
            headers=admin_headers,
            json={"work_days": [6, 7]},
        )
        assert response.status_code == 200
        assert response.json()["work_days"] == [6, 7]

        db.expire_all()
        assert db.get(Job, job.id).work_days == [1, 2, 3, 4, 5]

    def test_worker_switched_to_none_keeps_no_work_days(self, client, admin_headers, db):
        job, department = _job(db)
        worker_id = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={
                "name": "Стал почасовым",
                "email": "became-hourly@test.com",
                "department_id": department.id,
                "job_id": job.id,
            },
        ).json()["id"]

        response = client.put(
            f"/api/admin/workers/{worker_id}",
            headers=admin_headers,
            json={"schedule_type": "none"},
        )
        assert response.status_code == 200
        assert response.json()["work_days"] is None

    def test_empty_work_days_on_update_rejected(self, client, admin_headers, db):
        job, department = _job(db)
        worker_id = client.post(
            "/api/admin/workers",
            headers=admin_headers,
            json={
                "name": "Сломаем график",
                "email": "broken@test.com",
                "department_id": department.id,
                "job_id": job.id,
            },
        ).json()["id"]

        response = client.put(
            f"/api/admin/workers/{worker_id}",
            headers=admin_headers,
            json={"work_days": []},
        )
        assert response.status_code == 400
