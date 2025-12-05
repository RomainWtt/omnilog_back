from datetime import datetime
from typing import Optional, List, Any, Coroutine, Sequence, Dict
from uuid import UUID

from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_
from app.db.models import Friendship, FriendshipStatus


async def get_friendship(
        session: AsyncSession, user_id_a: UUID, user_id_b: UUID
) -> Optional[Friendship]:
    """
    Récupère une amitié, en vérifiant les deux ordres possibles (A vers B ou B vers A).
    C'est essentiel car vous n'avez pas normalisé l'ordre de stockage des IDs.
    """
    result = await session.execute(
        select(Friendship).where(
            or_(
                # Ordre A -> B
                (Friendship.user_one_id == user_id_a) & (Friendship.user_two_id == user_id_b),
                # Ordre B -> A
                (Friendship.user_one_id == user_id_b) & (Friendship.user_two_id == user_id_a)
            )
        )
    )
    return result.scalar_one_or_none()


async def create_friend_request(
        session: AsyncSession, sender_id: UUID, receiver_id: UUID
) -> Friendship:
    """Crée une nouvelle demande d'amitié (PENDING)."""

    # L'ordre d'insertion est (sender_id, receiver_id).
    friendship = Friendship(
        user_one_id=sender_id,
        user_two_id=receiver_id,
        status=FriendshipStatus.PENDING,
    )
    session.add(friendship)
    await session.commit()
    await session.refresh(friendship)
    return friendship


async def update_friendship_status(
        session: AsyncSession,
        user_id_a: UUID,
        user_id_b: UUID,
        new_status: FriendshipStatus
) -> Optional[Friendship]:
    """Met à jour le statut d'une amitié existante (trouvée dans les deux sens)."""

    friendship = await get_friendship(session, user_id_a, user_id_b)

    if not friendship:
        return None

    friendship.status = new_status
    friendship.updated_at = datetime.now()  # Met à jour la date
    await session.commit()
    await session.refresh(friendship)
    return friendship


async def get_user_relationships(
        session: AsyncSession,
        user_id: UUID, status: FriendshipStatus | None = None,
        limit: int = 20,
        offset: int = 0,
) -> Sequence[Friendship]:
    """
    Récupère les relations avec jointure des données utilisateur.
    """
    if status == FriendshipStatus.PENDING:
        query = (select(Friendship)
                 .where(
            (Friendship.user_two_id == user_id))
                 .limit(limit)
                 .offset(offset)
                 )
    else:
        query = (select(Friendship)
                 .where(
            or_(
                Friendship.user_one_id == user_id,
                Friendship.user_two_id == user_id
            )
        )
                 .limit(limit)
                 .offset(offset)
                 )

    if status is not None:
        query = query.where(Friendship.status == status)

    query = query.options(
        selectinload(Friendship.user_one),
        selectinload(Friendship.user_two)
    )

    result = await session.execute(query)
    return result.scalars().unique().all()


async def delete_friendship(
        session: AsyncSession, user_id_a: UUID, user_id_b: UUID
) -> bool:
    """Supprime une relation d'amitié (trouvée dans les deux sens)."""

    friendship = await get_friendship(session, user_id_a, user_id_b)

    if not friendship:
        return False

    await session.delete(friendship)
    await session.commit()
    return True


async def add_friends(
        session: AsyncSession, sender_id: UUID, receiver_id: UUID
) -> Friendship:
    """Crée une nouvelle demande d'amitié (PENDING)."""

    # L'ordre d'insertion est (sender_id, receiver_id).
    friendship = Friendship(
        user_one_id=sender_id,
        user_two_id=receiver_id,
        status=FriendshipStatus.ACCEPTED,
    )
    session.add(friendship)
    await session.commit()
    await session.refresh(friendship)
    return friendship


async def check_friendship_status(
        session: AsyncSession,
        current_user_id: UUID,
        target_user_ids: List[UUID]
) -> Dict[UUID, bool]:
    """
    Vérifie l'état d'amitié (ACCEPTED) entre l'utilisateur courant
    et une liste d'utilisateurs cibles, en une seule requête SQL.

    Args:
        session: La session de base de données.
        current_user_id: L'ID de l'utilisateur connecté (celui qui regarde).
        target_user_ids: La liste des IDs des utilisateurs à vérifier (commentateurs).

    Returns:
        Un dictionnaire {target_user_id: True} si la relation est ACCEPTED, sinon l'ID est absent.
    """

    target_ids_to_check = set(target_user_ids) - {current_user_id}

    if not target_ids_to_check:
        return {}

    condition_a_to_b = (Friendship.user_one_id == current_user_id) & (
        Friendship.user_two_id.in_(target_ids_to_check)
    )

    condition_b_to_a = (Friendship.user_one_id.in_(target_ids_to_check)) & (
            Friendship.user_two_id == current_user_id
    )

    query = select(Friendship).where(
        Friendship.status == FriendshipStatus.ACCEPTED,
        or_(condition_a_to_b, condition_b_to_a)
    )

    result = await session.execute(query)
    friendships: Sequence[Friendship] = result.scalars().all()

    friendship_map: Dict[UUID, bool] = {}

    for friendship in friendships:
        friend_id = (
            friendship.user_one_id
            if friendship.user_two_id == current_user_id
            else friendship.user_two_id
        )
        friendship_map[friend_id] = True

    return friendship_map
