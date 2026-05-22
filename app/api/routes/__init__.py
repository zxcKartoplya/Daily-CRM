from fastapi import APIRouter

from app.api.routes import (
    admin_analytics,
    admin_departments,
    admin_reports,
    admin_users,
    admin_workers,
    auth,
    employee_daily_reports,
    employee_profile,
    employee_settings,
    employee_statistics,
    internal_chat,
    jobs,
    reviewers,
)


router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["auth"], include_in_schema=True)
router.include_router(employee_profile.router, prefix="/employee/profile", tags=["employee-profile"], include_in_schema=True)
router.include_router(employee_settings.router, prefix="/employee/settings", tags=["employee-settings"], include_in_schema=True)
router.include_router(
    employee_daily_reports.router,
    prefix="/employee/daily-reports",
    tags=["employee-daily-reports"],
    include_in_schema=True,
)
router.include_router(
    employee_statistics.router,
    prefix="/employee/statistics",
    tags=["employee-statistics"],
    include_in_schema=True,
)
router.include_router(internal_chat.router, prefix="/employee/chat", tags=["employee-chat"], include_in_schema=True)
router.include_router(admin_users.router, prefix="/admin/users", tags=["admin-users"], include_in_schema=True)
router.include_router(
    admin_departments.router,
    prefix="/admin/departments",
    tags=["admin-departments"],
    include_in_schema=True,
)
router.include_router(jobs.router, prefix="/admin/jobs", tags=["admin-jobs"], include_in_schema=True)
router.include_router(admin_reports.router, prefix="/admin/reports", tags=["admin-reports"], include_in_schema=True)
router.include_router(
    admin_analytics.router,
    prefix="/admin/analytics",
    tags=["admin-analytics"],
    include_in_schema=True,
)
router.include_router(
    reviewers.router,
    prefix="/admin/reviewers",
    tags=["admin-reviewers"],
    include_in_schema=True,
)
