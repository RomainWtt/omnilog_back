from datetime import date, datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from sqlmodel import Field, Relationship, SQLModel


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


class FriendshipStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    BLOCKED = "blocked"


# Models
class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    avatar_url: Optional[str] = None
    
    # Relationships
    media_entries: list["UserMediaEntry"] = Relationship(back_populates="user")
    reviews: list["Review"] = Relationship(back_populates="user")
    initiated_friendships: list["Friendship"] = Relationship(
        back_populates="user_one",
        sa_relationship_kwargs={"foreign_keys": "Friendship.user_one_id"}
    )
    received_friendships: list["Friendship"] = Relationship(
        back_populates="user_two",
        sa_relationship_kwargs={"foreign_keys": "Friendship.user_two_id"}
    )


class Media(SQLModel, table=True):
    __tablename__ = "media"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tmdb_id: int = Field(unique=True, index=True)
    media_type: MediaType
    title: str
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    release_date: Optional[date] = None
    
    # Relationships
    user_entries: list["UserMediaEntry"] = Relationship(back_populates="media")
    reviews: list["Review"] = Relationship(back_populates="media")


class UserMediaEntry(SQLModel, table=True):
    __tablename__ = "user_media_entries"
    
    user_id: UUID = Field(foreign_key="users.id", primary_key=True)
    media_id: UUID = Field(foreign_key="media.id", primary_key=True)
    list_status: ListStatus
    progress: int = Field(default=0)
    score: Optional[int] = Field(default=None, ge=0, le=10)
    is_favorite: bool = Field(default=False)
    
    # Relationships
    user: User = Relationship(back_populates="media_entries")
    media: Media = Relationship(back_populates="user_entries")


class Review(SQLModel, table=True):
    __tablename__ = "reviews"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id")
    media_id: UUID = Field(foreign_key="media.id")
    content: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    user: User = Relationship(back_populates="reviews")
    media: Media = Relationship(back_populates="reviews")


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