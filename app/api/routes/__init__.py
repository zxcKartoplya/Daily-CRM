from fastapi import APIRouter

from app.api.routes import admins, departments, jobs, users, metrics, tasks, statistics, auth


router = APIRouter()

router.include_router(admins.router, prefix="/admins", tags=["admins"], include_in_schema=True)
router.include_router(auth.router, prefix="/auth", tags=["auth"], include_in_schema=True)
router.include_router(departments.router, prefix="/departments", tags=["departments"], include_in_schema=True)
router.include_router(jobs.router, prefix="/jobs", tags=["jobs"], include_in_schema=True)
router.include_router(users.router, prefix="/users", tags=["users"], include_in_schema=True)
router.include_router(metrics.router, prefix="/metrics", tags=["metrics"], include_in_schema=True)
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"], include_in_schema=True)
router.include_router(statistics.router, prefix="/statistics", tags=["statistics"], include_in_schema=True)
