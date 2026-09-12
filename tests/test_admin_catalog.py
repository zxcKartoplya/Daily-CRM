from app.models import Department, Job, Reviewer, User
from app.models.enums import UserRole, UserStatus


def _department(db, name="Разработка"):
    department = Department(name=name)
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


def _job(db, department, name="Бэкендер"):
    reviewer = Reviewer(name=f"Ревьюер {name}", description="описание")
    db.add(reviewer)
    db.flush()
    job = Job(name=name, department_id=department.id, reviewer_id=reviewer.id)
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


class TestWorkerJobName:
    def test_list_carries_job_name(self, client, db, admin_headers):
        department = _department(db)
        job = _job(db, department)
        db.add(
            User(
                name="Сотрудник",
                email="worker@test.com",
                role=UserRole.EMPLOYEE.value,
                status=UserStatus.ACTIVE.value,
                department_id=department.id,
                job_id=job.id,
            )
        )
        db.commit()

        body = client.get("/api/admin/workers", headers=admin_headers).json()
        assert body[0]["job_name"] == "Бэкендер"
        assert body[0]["department_name"] == "Разработка"

    def test_worker_without_job_has_null_name(self, client, db, admin_headers, employee_user):
        body = client.get("/api/admin/workers", headers=admin_headers).json()
        assert body[0]["job_name"] is None

    def test_worker_card_carries_job_name(self, client, db, admin_headers):
        department = _department(db)
        job = _job(db, department)
        worker = User(
            name="Сотрудник",
            email="worker@test.com",
            role=UserRole.EMPLOYEE.value,
            status=UserStatus.ACTIVE.value,
            department_id=department.id,
            job_id=job.id,
        )
        db.add(worker)
        db.commit()
        db.refresh(worker)

        body = client.get(f"/api/admin/workers/{worker.id}", headers=admin_headers).json()
        assert body["job_name"] == "Бэкендер"


class TestDepartmentCounters:
    def test_counters_are_independent(self, client, db, admin_headers):
        department = _department(db)
        _job(db, department, name="Бэкендер")
        _job(db, department, name="Фронтендер")
        db.add(
            User(
                name="Сотрудник",
                email="worker@test.com",
                role=UserRole.EMPLOYEE.value,
                status=UserStatus.ACTIVE.value,
                department_id=department.id,
            )
        )
        db.commit()

        body = client.get("/api/admin/departments", headers=admin_headers).json()
        assert body[0]["employees_count"] == 1
        assert body[0]["jobs_count"] == 2

        detail = client.get(f"/api/admin/departments/{department.id}", headers=admin_headers).json()
        assert detail["employees_count"] == 1
        assert detail["jobs_count"] == 2

    def test_new_department_starts_empty(self, client, admin_headers):
        created = client.post("/api/admin/departments", headers=admin_headers, json={"name": "Маркетинг"}).json()
        assert created["employees_count"] == 0
        assert created["jobs_count"] == 0
