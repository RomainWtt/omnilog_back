from typing import Any
from typing import Any
from uuid import UUID

from sqlalchemy import or_, exists, and_
from sqlmodel import select
from sqlmodel.sql._expression_select_cls import SelectOfScalar

from app.db.models import Review, User, ReviewReport, FriendshipStatus, Friendship


async def exclude_review_private(query, requesting_user_id: UUID | None) -> Any:
    if requesting_user_id is not None:
        query = query.where(
            or_(
                # Inclure les comptes publics
                User.is_public == True,
                # Inclure les propres commentaires de l'utilisateur
                Review.user_id == requesting_user_id,
                # Inclure les commentaires des amis (relation bidirectionnelle)
                exists(
                    select(1)
                    .select_from(Friendship)
                    .where(
                        and_(
                            or_(
                                # user_one est l'auteur et user_two est le demandeur
                                and_(
                                    Friendship.user_one_id == Review.user_id,
                                    Friendship.user_two_id == requesting_user_id
                                ),
                                # user_two est l'auteur et user_one est le demandeur
                                and_(
                                    Friendship.user_two_id == Review.user_id,
                                    Friendship.user_one_id == requesting_user_id
                                )
                            ),
                            Friendship.status == FriendshipStatus.ACCEPTED
                        )
                    )
                )
            )
        )
        # Joindre User pour accéder à is_public
        query = query.join(User, Review.user_id == User.id)
    return query


async def exclude_report_review(exclude_reported_by: UUID | None, query: SelectOfScalar[int]) -> SelectOfScalar[int]:
    if exclude_reported_by is not None:
        query = query.where(
            ~exists(
                select(1)
                .select_from(ReviewReport)
                .where(ReviewReport.review_id == Review.id)
                .where(ReviewReport.reporter_id == exclude_reported_by)
            )
        )
    return query
