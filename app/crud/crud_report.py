from typing import Optional, List
from uuid import UUID, uuid4
from datetime import datetime
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from app.db.models import ReviewReport, Review


async def get_report_by_id(session: AsyncSession, report_id: UUID) -> Optional[ReviewReport]:
    result = await session.execute(select(ReviewReport).where(ReviewReport.id == report_id))
    return result.scalar_one_or_none()


async def get_reports_for_review(session: AsyncSession, review_id: UUID) -> List[ReviewReport]:
    result = await session.execute(select(ReviewReport).where(ReviewReport.review_id == review_id))
    return list(result.scalars().all())


async def get_all_reports(session: AsyncSession) -> List[ReviewReport]:
    result = await session.execute(select(ReviewReport).order_by(ReviewReport.created_at.desc()))
    return list(result.scalars().all())


async def create_report(
    session: AsyncSession,
    reporter_id: UUID,
    review_id: UUID,
    reason: str
) -> ReviewReport:
    """Create a new report"""

    # Vérifier que la review existe
    result = await session.execute(select(Review).where(Review.id == review_id))
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(404, "Review not found")

    # Interdire le report de sa propre review
    if review.user_id == reporter_id:
        raise HTTPException(400, "Cannot report your own review")

    # Vérifier doublon
    result = await session.execute(
        select(ReviewReport).where(
            ReviewReport.reporter_id == reporter_id,
            ReviewReport.review_id == review_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "You have already reported this review")

    report = ReviewReport(
        id=uuid4(),
        reporter_id=reporter_id,
        review_id=review_id,
        reported_user_id=review.user_id,
        reason=reason,
        created_at=datetime.utcnow()
    )

    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def update_report(
    session: AsyncSession,
    report_id: UUID,
    **update_data
) -> Optional[ReviewReport]:
    report = await get_report_by_id(session, report_id)
    if not report:
        return None

    for key, value in update_data.items():
        if hasattr(report, key) and value is not None:
            setattr(report, key, value)

    report.created_at = datetime.utcnow()
    await session.commit()
    await session.refresh(report)
    return report


async def delete_report(session: AsyncSession, report_id: UUID) -> bool: # TODO a garer ?
    report = await get_report_by_id(session, report_id)
    if not report:
        return False

    await session.delete(report)
    await session.commit()
    return True
