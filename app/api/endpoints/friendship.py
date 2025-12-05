# app/api/v1/friendships.py

import uuid
from typing import List

from fastapi import APIRouter, Query, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_active_user
from app.crud import crud_friendship
from app.crud.crud_activity import add_accept_friend
from app.db.models import NotificationType
from app.db.session import get_session
from app.schemas.friendship import FriendshipStatus, FriendshipUpdate, \
    FriendProfileRead, FriendshipReadSimple
from app.schemas.user import UserRead
from app.services.notification_service import notification_service
router = APIRouter()


@router.post(
    "/",
    response_model=FriendshipReadSimple,
    status_code=status.HTTP_201_CREATED,
    summary="Envoie une demande d'amitié (PENDING)."
)
async def send_friend_request(
    user_two_id: str,
    is_public: bool = False,
    current_user: UserRead = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    sender_id = current_user.id
    receiver_id = uuid.UUID(user_two_id)

    if sender_id == receiver_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User cannot send a friend request to yourself."
        )

    # 1. Vérifier si une relation existe déjà
    existing_friendship = await crud_friendship.get_friendship(
        session, sender_id, receiver_id
    )

    if existing_friendship:
        if existing_friendship.status == FriendshipStatus.PENDING:
            if existing_friendship.user_one_id == sender_id:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Friend request already sent and pending."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Friend request already received and pending. Please use PUT to accept/decline."
                )

        if existing_friendship.status == FriendshipStatus.ACCEPTED:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Users are already friends."
            )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A relationship in status {existing_friendship.status.value} already exists."
        )

    if is_public:
        friendship = await crud_friendship.add_friends(
            session, sender_id, receiver_id
        )
        return friendship

    # 2. Créer la demande
    friendship = await crud_friendship.create_friend_request(
        session, sender_id, receiver_id
    )

    # 3. 🆕 Envoyer la notification via le service (1 ligne !)
    await notification_service.send_notification(
        session=session,
        user_id=receiver_id,
        actor_id=sender_id,
        notification_type=NotificationType.FRIEND_REQUEST,
        data={"friendship_id": str(friendship.user_one_id)}
    )

    return friendship


@router.put(
    "/{user_id}",
    response_model=FriendshipReadSimple,
    summary="Met à jour le statut d'une demande d'amitié (ACCEPT/DECLINE/BLOCK)."
)
async def update_friendship_status(
    user_id: uuid.UUID,
    new_status: FriendshipUpdate,
    current_user: UserRead = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_session),
):
    current_user_id = current_user.id

    # 1. Récupération de la relation
    friendship = await crud_friendship.get_friendship(
        session, current_user_id, user_id
    )

    if not friendship:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friendship not found."
        )

    # 2. Cas BLOCKED
    if new_status.status == FriendshipStatus.BLOCKED:
        updated_friendship = await crud_friendship.update_friendship_status(
            session,
            friendship.user_one_id,
            friendship.user_two_id,
            FriendshipStatus.BLOCKED
        )
        return updated_friendship

    # 3. Cas ACCEPT / DECLINE
    if friendship.status == FriendshipStatus.PENDING:
        if friendship.user_one_id == current_user_id:
            if new_status.status in (FriendshipStatus.ACCEPTED, FriendshipStatus.DECLINED):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only the recipient can manage a pending request."
                )
        elif friendship.user_two_id == current_user_id:
            if new_status.status not in (FriendshipStatus.ACCEPTED, FriendshipStatus.DECLINED):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Recipient can only ACCEPT or DECLINE a pending request."
                )
    else:
        if new_status.status in (FriendshipStatus.ACCEPTED, FriendshipStatus.DECLINED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot accept or decline a non-pending relationship."
            )

    # 4. Mise à jour
    updated_friendship = await crud_friendship.update_friendship_status(
        session,
        friendship.user_one_id,
        friendship.user_two_id,
        new_status.status
    )

    # 5. 🆕 Si accepté, notifier l'initiateur (1 ligne !)
    if new_status.status == FriendshipStatus.ACCEPTED:
        await notification_service.send_notification(
            session=session,
            user_id=friendship.user_one_id,
            actor_id=current_user_id,
            notification_type=NotificationType.FRIEND_ACCEPTED,
            data={"friendship_id": str(friendship.user_one_id)}
        )

        if updated_friendship.user_two:
            result = await add_accept_friend(session, friendship)
            print(result)

        # 🆕 Notifier si refusé
    elif new_status.status == FriendshipStatus.DECLINED:
        await notification_service.send_notification(
            session=session,
            user_id=friendship.user_one_id,
            actor_id=current_user_id,
            notification_type=NotificationType.FRIEND_DECLINED,
            data={"friendship_id": str(friendship.user_one_id)}
        )

    return updated_friendship


# --- GET /api/v1/friendships/?status=... ---

@router.get(
    "/friends",
    response_model=List[FriendProfileRead],
    summary="Récupère les relations de l'utilisateur authentifié, filtrées par statut."
)
async def get_user_friends_list(
        current_user: UserRead = Depends(get_current_active_user),
        status: FriendshipStatus = Query(FriendshipStatus.ACCEPTED),
        page: int = Query(1, ge=1, description="Page number"),
        session: AsyncSession = Depends(get_session),
):
    PAGE_SIZE = 20
    offset = (page - 1) * PAGE_SIZE
    user_id = current_user.id

    friendships = await crud_friendship.get_user_relationships(
        session, user_id,
        status=status,
        limit=PAGE_SIZE,
        offset=offset
    )

    if not friendships:
        return []

    friends_list = []
    current_user_id = user_id

    for friendship in friendships:
        if friendship.user_one.id == current_user_id:
            friend = friendship.user_two
        elif friendship.user_two.id == current_user_id:
            friend = friendship.user_one
        else:
            continue

        friends_list.append(FriendProfileRead.model_validate(friend))

    return friends_list


@router.get(
    "/pending",
    response_model=List[FriendProfileRead],  # Utiliser le schéma enrichi pour indiquer l'expéditeur
    summary="Récupère toutes les demandes d'amitié en attente (reçues)."
)
async def get_pending_friend_requests(
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """
    Récupère une liste des utilisateurs impliqués dans une relation PENDING,
    indiquant si la demande est reçue (à accepter) ou envoyée (à annuler).
    """
    print("Récupération des pending requests")
    user_id = current_user.id

    # 1. Récupérer uniquement les relations PENDING (reçues ET envoyées)
    friendships = await crud_friendship.get_user_relationships(
        session, user_id, status=FriendshipStatus.PENDING
    )

    if not friendships:
        return []

    # 2. Transformer les relations en liste d'objets PendingRequestRead
    pending_requests_list = []
    current_user_id = user_id

    for friendship in friendships:
        # Déterminer qui est l'autre utilisateur et si la demande a été envoyée par l'utilisateur courant

        is_sender = friendship.user_one.id == current_user_id

        if is_sender:
            # L'utilisateur courant est user_one (expéditeur). L'autre est user_two.
            other_user = friendship.user_two
        else:
            # L'utilisateur courant est user_two (destinataire). L'autre est user_one.
            other_user = friendship.user_one

        # Créer l'objet simplifié PendingRequestRead
        request_data = FriendProfileRead.model_validate(other_user)

        pending_requests_list.append(request_data)

    return pending_requests_list


# --- DELETE /api/v1/friendships/{user_id} ---

@router.delete(
    "/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Supprime une relation (Annulation de demande, ou Unfriend)."
)
async def delete_friendship(
        user_id: uuid.UUID,
        current_user: UserRead = Depends(get_current_active_user),
        session: AsyncSession = Depends(get_session),
):
    """
    Permet à l'utilisateur authentifié de supprimer définitivement une relation.
    (ex: annuler une demande PENDING, ou supprimer une relation ACCEPTED/DECLINED/BLOCKED).
    """
    current_user_id = current_user.id

    deleted = await crud_friendship.delete_friendship(session, current_user_id, user_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Friendship not found or already deleted."
        )

    return
