from fastapi import APIRouter

from app.api.routes import admins, departments, jobs, users, metrics, tasks, statistics


router = APIRouter()

router.include_router(admins.router, prefix="/admins", tags=["admins"])
router.include_router(departments.router, prefix="/departments", tags=["departments"])
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"])
router.include_router(users.router, prefix="/users", tags=["users"])
router.include_router(metrics.router, prefix="/metrics", tags=["metrics"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(statistics.router, prefix="/statistics", tags=["statistics"])
