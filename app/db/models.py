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


class GroupType(str, Enum):
    PUBLIC_GLOBAL = "public_global"  # Created by admins
    PUBLIC_COMMUNITY = "public_community"  # Created by users
    PRIVATE = "private"  # Invitation only


class ActivityType(str, Enum):
    MEDIA_ADDED = "media_added"
    MEDIA_COMPLETED = "media_completed"
    MEDIA_PROGRESS = "media_progress"
    REVIEW_POSTED = "review_posted"
    COMMENT_ADDED = "comment_added"
    FRIEND_ADDED = "friend_added"
    GROUP_JOINED = "group_joined"
    CHALLENGE_JOINED = "challenge_joined"


# Models
class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    email: str = Field(unique=True, index=True, max_length=255)
    hashed_password: Optional[str] = None  # Optional for OAuth users
    avatar_url: Optional[str] = None
    birth_date: Optional[date] = None
    is_active: bool = Field(default=True)
    is_admin: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # OAuth providers
    google_id: Optional[str] = Field(default=None, unique=True, index=True)
    facebook_id: Optional[str] = Field(default=None, unique=True, index=True)
    apple_id: Optional[str] = Field(default=None, unique=True, index=True)
    
    # Social media links
    social_links: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    # Relationships
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
    group_memberships: list["GroupMembership"] = Relationship(back_populates="user")
    challenge_participations: list["ChallengeParticipation"] = Relationship(back_populates="user")


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
    
    # Movie specific
    runtime: Optional[int] = None  # In minutes
    
    # TV specific
    number_of_seasons: Optional[int] = None
    number_of_episodes: Optional[int] = None
    episode_run_time: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))
    
    # Common
    genres: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    production_companies: Optional[list[str]] = Field(default=None, sa_column=Column(JSON))
    original_language: Optional[str] = None
    popularity: Optional[float] = None
    vote_average: Optional[float] = None
    vote_count: Optional[int] = None
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user_entries: list["UserMediaEntry"] = Relationship(back_populates="media")
    reviews: list["Review"] = Relationship(back_populates="media")
    comments: list["Comment"] = Relationship(back_populates="media")


class UserMediaEntry(SQLModel, table=True):
    __tablename__ = "user_media_entries"
    
    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    media_id: UUID = Field(foreign_key="media.id", primary_key=True)
    list_status: ListStatus = Field(default=ListStatus.PLAN_TO_WATCH)
    
    # Progress tracking
    progress: int = Field(default=0)  # Episode number for TV, percentage for movies
    current_season: Optional[int] = Field(default=None)  # For TV shows
    current_episode: Optional[int] = Field(default=None)  # For TV shows
    timecode: Optional[int] = Field(default=0)  # In seconds
    
    # Rating
    score: Optional[int] = Field(default=None, ge=0, le=10)
    
    # Favorites
    is_favorite: bool = Field(default=False)
    
    # Timestamps
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="media_entries")
    media: Media = Relationship(back_populates="user_entries")


class Review(SQLModel, table=True):
    """Public reviews visible to all users"""
    __tablename__ = "reviews"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    media_id: UUID = Field(foreign_key="media.id", index=True)
    content: str = Field(max_length=5000)
    rating: Optional[int] = Field(default=None, ge=0, le=5)  # 0-5 stars
    is_visible: bool = Field(default=True)  # For moderation
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="reviews")
    media: Media = Relationship(back_populates="reviews")


class Comment(SQLModel, table=True):
    """Private personal notes on media"""
    __tablename__ = "comments"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    media_id: UUID = Field(foreign_key="media.id", index=True)
    content: str = Field(max_length=5000)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="comments")
    media: Media = Relationship(back_populates="comments")


class Friendship(SQLModel, table=True):
    __tablename__ = "friendships"
    
    user_one_id: UUID = Field(foreign_key="users.id", primary_key=True)
    user_two_id: UUID = Field(foreign_key="users.id", primary_key=True)
    status: FriendshipStatus = Field(default=FriendshipStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user_one: User = Relationship(
        back_populates="initiated_friendships",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_one_id]"}
    )
    user_two: User = Relationship(
        back_populates="received_friendships",
        sa_relationship_kwargs={"foreign_keys": "[Friendship.user_two_id]"}
    )


class Group(SQLModel, table=True):
    """Groups/Challenges"""
    __tablename__ = "groups"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(max_length=100, index=True)
    description: Optional[str] = Field(max_length=1000)
    group_type: GroupType
    avatar_url: Optional[str] = None
    
    # Challenge specific
    is_challenge: bool = Field(default=False)
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    media_list: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))  # List of TMDB IDs
    
    # Creator
    creator_id: UUID = Field(foreign_key="users.id", index=True)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    memberships: list["GroupMembership"] = Relationship(back_populates="group")


class GroupMembership(SQLModel, table=True):
    """User membership in groups"""
    __tablename__ = "group_memberships"
    
    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    group_id: UUID = Field(foreign_key="groups.id", primary_key=True)
    is_admin: bool = Field(default=False)
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="group_memberships")
    group: Group = Relationship(back_populates="memberships")


class ChallengeParticipation(SQLModel, table=True):
    """Track user progress in challenges"""
    __tablename__ = "challenge_participations"
    
    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    group_id: UUID = Field(foreign_key="groups.id", primary_key=True)
    progress: int = Field(default=0)  # Number of media completed
    rank: Optional[int] = None
    completed_media: Optional[list[int]] = Field(default=None, sa_column=Column(JSON))  # TMDB IDs
    joined_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="challenge_participations")


class Activity(SQLModel, table=True):
    """User activity tracking for history"""
    __tablename__ = "activities"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    activity_type: ActivityType
    
    # Activity details
    details: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    # Relationships
    user: User = Relationship(back_populates="activities")
