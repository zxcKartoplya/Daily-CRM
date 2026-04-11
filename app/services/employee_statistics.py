from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.api.schemas.analytics import EmployeeStatistics
from app.models import DailyReport as DailyReportModel


def calculate_employee_statistics(db: Session, user_id: int) -> EmployeeStatistics:
    reports = (
        db.query(DailyReportModel)
        .filter(DailyReportModel.user_id == user_id)
        .order_by(DailyReportModel.report_date.desc())
        .all()
    )

    streak = _calculate_streak([report.report_date for report in reports])
    last_30_days = date.today() - timedelta(days=29)
    reports_last_30 = [report for report in reports if report.report_date >= last_30_days]
    completion_rate = round(len(reports_last_30) / 30, 4)

    ratings = [report.self_rating for report in reports if report.self_rating is not None]
    average_self_rating = round(sum(ratings) / len(ratings), 2) if ratings else None

    blockers_count = sum(1 for report in reports if report.blockers_text and report.blockers_text.strip())
    last_report_at = reports[0].submitted_at if reports else None

    return EmployeeStatistics(
        user_id=user_id,
        streak=streak,
        completion_rate=completion_rate,
        average_self_rating=average_self_rating,
        blockers_count=blockers_count,
        last_report_at=last_report_at,
    )


def _calculate_streak(report_dates: list[date]) -> int:
    if not report_dates:
        return 0

    unique_dates = sorted(set(report_dates), reverse=True)
    streak = 1
    previous = unique_dates[0]
    for current in unique_dates[1:]:
        if previous - current == timedelta(days=1):
            streak += 1
            previous = current
            continue
        break
    return streak
