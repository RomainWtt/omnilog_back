from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel, Column, JSON


# Enums
class MediaType(str, Enum):
    MOVIE = "movie"
    TV = "tv"


class ListStatus(str, Enum):
    WATCHING = "watching"
    COMPLETED = "completed"
    PLAN_TO_WATCH = "plan_to_watch"
    DROPPED = "dropped"
    ON_HOLD = "on_hold"
    FAVORITE = "favorite"


class FriendshipStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    BLOCKED = "blocked"


class ChallengeType(str, Enum):
    PUBLIC_GLOBAL = "public_global"
    PUBLIC_COMMUNITY = "public_community"
    PRIVATE = "private"


class ChallengeStatus(str, Enum):
    TOUS = "tous"
    A_VENIR = "a_venir"
    EN_COURS = "en_cours"
    TERMINE = "termine"


class ActivityType(str, Enum):
    MEDIA_ADDED = "media_added"
    MEDIA_COMPLETED = "media_completed"
    MEDIA_PROGRESS = "media_progress"
    REVIEW_POSTED = "review_posted"
    FRIEND_ADDED = "friend_added"
    CHALLENGE_JOINED = "challenge_joined"
    CHALLENGE_COMPLETED_EPISODE = "challenge_completed_episode"
    CHALLENGE_MILESTONE = "challenge_milestone"
    CHALLENGE_LEFT = "challenge_left"
    CHALLENGE_FINISHED = "challenge_finished"


# Models
class User(SQLModel, table=True):
    __tablename__ = "users"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: Optional[str] = None
    avatar_url: Optional[str] = None
    birth_date: Optional[date] = None

    # Séparation des responsabilités
    is_active: bool = Field(default=True)  # Compte actif/désactivé (admin)
    email_verified: bool = Field(default=False)  # Email vérifié (utilisateur)

    is_admin: bool = Field(default=False)
    is_public: bool = Field(default=True)

    # Tokens de vérification d'email
    email_verification_token: Optional[str] = Field(default=None, max_length=64)
    email_verification_token_expires: Optional[datetime] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    google_id: Optional[str] = Field(default=None, unique=True, index=True)
    facebook_id: Optional[str] = Field(default=None, unique=True, index=True)
    apple_id: Optional[str] = Field(default=None, unique=True, index=True)

    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    notification_preferences: Optional[dict] = Field(
        default_factory=lambda: {
            "friend_request": True,
            "friend_accepted": True,
            "friend_declined": True,
            "favorite_added": True,
            "review_posted": True,
            "challenge": True
        },
        sa_column=Column(JSON)
    )

    media_entries: list["UserMediaEntry"] = Relationship(back_populates="user")
    reviews: list["Review"] = Relationship(back_populates="user")
    activities: list["Activity"] = Relationship(back_populates="user")
    initiated_friendships: list["Friendship"] = Relationship(
        back_populates="user_one",
        sa_relationship_kwargs={"foreign_keys": "Friendship.user_one_id"}
    )
    received_friendships: list["Friendship"] = Relationship(
        back_populates="user_two",
        sa_relationship_kwargs={"foreign_keys": "Friendship.user_two_id"}
    )
    challenge_memberships: list["ChallengeMembership"] = Relationship(back_populates="user")
    reported_reviews: list["ReviewReport"] = Relationship(
        back_populates="reporter",
        sa_relationship_kwargs={"foreign_keys": "ReviewReport.reporter_id"}
    )
    received_reports: list["ReviewReport"] = Relationship(
        back_populates="reported_user",
        sa_relationship_kwargs={"foreign_keys": "ReviewReport.reported_user_id"}
    )


class Genre(SQLModel, table=True):
    """Genre with composite PK - SIMPLIFIED for SQLite"""
    __tablename__ = "genres"

    id: int = Field(primary_key=True)
    media_type: MediaType = Field(primary_key=True)
    name: str = Field(max_length=100)

    # Removed relationship - handle manually in code


class Media(SQLModel, table=True):
    __tablename__ = "media"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tmdb_id: int = Field(unique=True, index=True)
    media_type: MediaType
    title: str = Field(index=True)
    original_title: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    backdrop_path: Optional[str] = None
    release_date: Optional[date] = None

    runtime: Optional[int] = None

    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None
    episode_run_time: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))

    # Store genre IDs as JSON for simplicity
    genre_ids: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    production_companies: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    actors: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    directors: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    original_language: Optional[str] = Field(default="fr-BE")
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    translations: dict = Field(
        default_factory=dict,
        sa_column=Column(JSON().with_variant(JSONB, "postgresql"))
    )

    user_entries: list["UserMediaEntry"] = Relationship(back_populates="media")
    reviews: list["Review"] = Relationship(back_populates="media")


class UserMediaEntry(SQLModel, table=True):
    __tablename__ = "user_media_entries"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    media_id: UUID = Field(foreign_key="media.id", primary_key=True)
    list_status: ListStatus = Field(default=ListStatus.PLAN_TO_WATCH)

    current_season: Optional[int] = Field(default=None)
    current_episode: Optional[int] = Field(default=None)
    timecode: Optional[int] = Field(default=0)

    score: Optional[int] = Field(default=None, ge=0, le=10)
    is_favorite: bool = Field(default=False)

    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="media_entries")
    media: Media = Relationship(back_populates="user_entries")



class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    media_id: UUID = Field(foreign_key="media.id", index=True)
    content: Optional[str] = Field(default=None, max_length=5000)
    rating: int = Field(ge=1, le=5)
    is_visible: bool = Field(default=True)
    is_report : bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="reviews")
    media: Media = Relationship(back_populates="reviews")
    reports: list["ReviewReport"] = Relationship(back_populates="review")



class ReviewReport(SQLModel, table=True):
    __tablename__ = "review_reports"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    reporter_id: UUID = Field(foreign_key="users.id", index=True)
    reported_user_id: UUID = Field(foreign_key="users.id", index=True)
    review_id: UUID = Field(foreign_key="reviews.id", index=True)
    reason: str = Field(max_length=1000)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    reporter: User = Relationship(
        back_populates="reported_reviews",
        sa_relationship_kwargs={"foreign_keys": "[ReviewReport.reporter_id]"}
    )
    reported_user: User = Relationship(
        back_populates="received_reports",
        sa_relationship_kwargs={"foreign_keys": "[ReviewReport.reported_user_id]"}
    )
    review: Review = Relationship(back_populates="reports")


class Friendship(SQLModel, table=True):
    __tablename__ = "friendships"

    user_one_id: UUID = Field(foreign_key="users.id", primary_key=True)
    user_two_id: UUID = Field(foreign_key="users.id", primary_key=True)
    status: FriendshipStatus = Field(default=FriendshipStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user_one: User = Relationship(
        back_populates="initiated_friendships",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_one_id]"}
    )
    user_two: User = Relationship(
        back_populates="received_friendships",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_two_id]"}
    )


class Challenge(SQLModel, table=True):
    __tablename__ = "challenges"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100, index=True)
    description: Optional[str] = Field(max_length=1000)
    challenge_type: ChallengeType
    avatar_url: Optional[str] = None

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    #media_list: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    media_list: Optional[list[dict]] = Field(default_factory=list, sa_column=Column(JSON))

    creator_id: UUID = Field(foreign_key="users.id", index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    memberships: list["ChallengeMembership"] = Relationship(back_populates="challenge")


class ChallengeMembership(SQLModel, table=True):
    __tablename__ = "challenge_memberships"

    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    challenge_id: UUID = Field(foreign_key="challenges.id", primary_key=True)
    is_admin: bool = Field(default=False)
    progress: int = Field(default=0)
    rank: Optional[int] = None
    completed_media: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="challenge_memberships")
    challenge: Challenge = Relationship(back_populates="memberships")


class Activity(SQLModel, table=True):
    __tablename__ = "activities"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    activity_type: ActivityType

    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    user: User = Relationship(back_populates="activities")

# À Notifications

class NotificationType(str, Enum):
    FRIEND_REQUEST = "friend_request"
    FRIEND_ACCEPTED = "friend_accepted"
    FRIEND_DECLINED = "friend_declined"
    FAVORITE_ADDED = "favorite_added"
    REVIEW_POSTED = "review_posted"
    #CHALLENGE_INVITATION = "challenge_invitation"
    #CHALLENGE_ACCEPTED = "challenge_accepted"
    #CHALLENGE_DECLINED = "challenge_declined"
    CHALLENGE = "challenge"

class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)  # Destinataire
    actor_id: Optional[UUID] = Field(default=None, foreign_key="users.id")  # Celui qui fait l'action

    notification_type: NotificationType

    # Données contextuelles (JSON flexible)
    data: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    read: bool = Field(default=False, index=True)  # Index pour filtrer rapidement

    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # Relations
    user: User = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Notification.user_id]"}
    )
    actor: Optional[User] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "[Notification.actor_id]"}
    )