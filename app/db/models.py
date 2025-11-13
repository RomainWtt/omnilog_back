from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

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


class ActivityType(str, Enum):
    MEDIA_ADDED = "media_added"
    MEDIA_COMPLETED = "media_completed"
    MEDIA_PROGRESS = "media_progress"
    REVIEW_POSTED = "review_posted"
    COMMENT_ADDED = "comment_added"
    FRIEND_ADDED = "friend_added"
    CHALLENGE_JOINED = "challenge_joined"


# Models
class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: Optional[str] = None
    avatar_url: Optional[str] = None
    birth_date: Optional[date] = None
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    is_public: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    google_id: Optional[str] = Field(default=None, unique=True, index=True)
    facebook_id: Optional[str] = Field(default=None, unique=True, index=True)
    apple_id: Optional[str] = Field(default=None, unique=True, index=True)
    
    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    media_entries: list["UserMediaEntry"] = Relationship(back_populates="user")
    reviews: list["Review"] = Relationship(back_populates="user")
    comments: list["Comment"] = Relationship(back_populates="user")
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
    original_language: Optional[str] = Field(default="fr-BE")
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    user_entries: list["UserMediaEntry"] = Relationship(back_populates="media")
    reviews: list["Review"] = Relationship(back_populates="media")
    comments: list["Comment"] = Relationship(back_populates="media")


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
    content: str = Field(max_length=5000)
    rating: Optional[int] = Field(default=None, ge=0, le=5)
    is_visible: bool = Field(default=True)
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


class Comment(SQLModel, table=True):
    __tablename__ = "comments"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    media_id: UUID = Field(foreign_key="media.id", index=True)
    content: str = Field(max_length=5000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    user: User = Relationship(back_populates="comments")
    media: Media = Relationship(back_populates="comments")


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
    media_list: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    
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
