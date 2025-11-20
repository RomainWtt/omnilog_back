from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID, uuid4
from datetime import datetime
from fastapi import HTTPException
from app.db.models import ReviewReport, Review

async def create_report(
    session: AsyncSession,
    reporter_id: UUID,
    review_id: UUID,
    reported_user_id: UUID,
    reason: str
) -> ReviewReport:

    result = await session.execute(
        select(Review).where(Review.id == review_id)
    )
    review = result.scalar_one_or_none()
    if not review:
        raise HTTPException(404, "Review introuvable")

    if review.user_id == reporter_id:
        raise HTTPException(400, "Tu ne peux pas signaler ta propre review")

    result = await session.execute(
        select(ReviewReport)
        .where(
            ReviewReport.reporter_id == reporter_id,
            ReviewReport.review_id == review_id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(400, "Tu as déjà signalé cette review")

    report = ReviewReport(
        id=uuid4(),
        reporter_id=reporter_id,
        review_id=review_id,
        reported_user_id=reported_user_id,
        reason=reason,
        created_at=datetime.utcnow()
    )

    session.add(report)
    await session.commit()
    await session.refresh(report)
    return report


async def get_reports_for_review(session: AsyncSession, review_id: UUID):
    result = await session.execute(
        select(ReviewReport).where(ReviewReport.review_id == review_id)
    )
    return result.scalars().all()
