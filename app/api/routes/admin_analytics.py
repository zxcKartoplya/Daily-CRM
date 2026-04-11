from datetime import date, timedelta
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.dependencies import require_admin_user
from app.api.schemas.analytics import AnalyticsOverview, DepartmentAnalytics
from app.db.session import get_db
from app.models import DailyReport as DailyReportModel
from app.models import Department as DepartmentModel
from app.models import User as UserModel
from app.models.enums import UserRole


router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
def get_admin_analytics_overview(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> AnalyticsOverview:
    employees_count = db.query(UserModel).filter(UserModel.role == UserRole.EMPLOYEE.value).count()
    departments_count = db.query(DepartmentModel).count()
    reports_count = db.query(DailyReportModel).count()
    today = date.today()
    reports_today = db.query(DailyReportModel).filter(DailyReportModel.report_date == today).count()
    needs_help_count = db.query(DailyReportModel).filter(DailyReportModel.needs_help.is_(True)).count()
    average_self_rating = db.query(func.avg(DailyReportModel.self_rating)).scalar()
    last_report_at = db.query(func.max(DailyReportModel.submitted_at)).scalar()

    last_30_start = today - timedelta(days=29)
    last_30_reports = (
        db.query(DailyReportModel)
        .filter(DailyReportModel.report_date >= last_30_start)
        .count()
    )
    expected_reports = employees_count * 30
    completion_rate = round(last_30_reports / expected_reports, 4) if expected_reports else 0.0

    return AnalyticsOverview(
        employees_count=employees_count,
        departments_count=departments_count,
        reports_count=reports_count,
        reports_today=reports_today,
        needs_help_count=needs_help_count,
        average_self_rating=round(float(average_self_rating), 2) if average_self_rating is not None else None,
        last_report_at=last_report_at,
        completion_rate_last_30_days=completion_rate,
    )


@router.get("/departments", response_model=List[DepartmentAnalytics])
def get_department_analytics(
    db: Session = Depends(get_db),
    _: UserModel = Depends(require_admin_user),
) -> List[DepartmentAnalytics]:
    employee_counts = (
        db.query(
            UserModel.department_id.label("department_id"),
            func.count(UserModel.id).label("employees_count"),
        )
        .filter(UserModel.role == UserRole.EMPLOYEE.value)
        .group_by(UserModel.department_id)
        .subquery()
    )
    report_stats = (
        db.query(
            DailyReportModel.department_id.label("department_id"),
            func.count(DailyReportModel.id).label("reports_count"),
            func.avg(DailyReportModel.self_rating).label("average_self_rating"),
            func.sum(case((DailyReportModel.needs_help.is_(True), 1), else_=0)).label("needs_help_count"),
        )
        .group_by(DailyReportModel.department_id)
        .subquery()
    )
    rows = (
        db.query(
            DepartmentModel.id,
            DepartmentModel.name,
            employee_counts.c.employees_count,
            report_stats.c.reports_count,
            report_stats.c.average_self_rating,
            report_stats.c.needs_help_count,
        )
        .outerjoin(employee_counts, employee_counts.c.department_id == DepartmentModel.id)
        .outerjoin(report_stats, report_stats.c.department_id == DepartmentModel.id)
        .order_by(DepartmentModel.name.asc())
        .all()
    )

    return [
        DepartmentAnalytics(
            department_id=department_id,
            department_name=department_name,
            employees_count=int(employees_count or 0),
            reports_count=int(reports_count or 0),
            average_self_rating=round(float(average_self_rating), 2) if average_self_rating is not None else None,
            needs_help_count=int(needs_help_count or 0),
        )
        for department_id, department_name, employees_count, reports_count, average_self_rating, needs_help_count in rows
    ]
