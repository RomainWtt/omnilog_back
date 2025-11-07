"""
Database seeding script for Omnilog backend
SAFE FOR PRODUCTION - only runs in dev/test environments
"""
import asyncio
import os
from datetime import datetime, date, timedelta
from uuid import uuid4
from dotenv import load_dotenv
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

# Load .env file FIRST
load_dotenv()

from app.db.session import async_session_maker
from app.db.models import (
    User, Media, MediaType, UserMediaEntry, ListStatus,
    Review, Comment, Friendship, FriendshipStatus,
    Group, GroupType, GroupMembership, Activity, ActivityType
)
from app.core.security import get_password_hash


# Environment check
def is_safe_environment() -> bool:
    """Check if we're in dev/test environment"""
    env = os.getenv("ENVIRONMENT", "production").lower()
    db_url = os.getenv("DATABASE_URL", "")
    
    # Don't run in production
    if env == "production" or "prod" in db_url.lower():
        return False
    
    # Allow dev, test, local environments
    return env in ["development", "dev", "test", "testing", "local"]


# Seed data
SEED_USERS = [
    {
        "username": "admin",
        "email": "admin@omnilog.com",
        "password": "Admin123!",
        "is_admin": True,
        "birth_date": date(1990, 1, 1)
    },
    {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "User123!",
        "birth_date": date(1995, 6, 15)
    },
    {
        "username": "jane_smith",
        "email": "jane@example.com",
        "password": "User123!",
        "birth_date": date(1992, 3, 20)
    },
    {
        "username": "movie_buff",
        "email": "buff@example.com",
        "password": "User123!",
        "birth_date": date(1988, 11, 8)
    }
]

SEED_MOVIES = [
    {
        "tmdb_id": 550,
        "media_type": MediaType.MOVIE,
        "title": "Fight Club",
        "overview": "A ticking-time-bomb insomniac and a slippery soap salesman channel primal male aggression.",
        "release_date": date(1999, 10, 15),
        "runtime": 139,
        "genres": ["Drama", "Thriller"],
        "original_language": "en",
        "popularity": 85.2,
        "vote_average": 8.4,
        "vote_count": 28000
    },
    {
        "tmdb_id": 238,
        "media_type": MediaType.MOVIE,
        "title": "The Godfather",
        "overview": "The aging patriarch of an organized crime dynasty transfers control to his reluctant son.",
        "release_date": date(1972, 3, 24),
        "runtime": 175,
        "genres": ["Drama", "Crime"],
        "original_language": "en",
        "popularity": 92.1,
        "vote_average": 8.7,
        "vote_count": 19000
    },
    {
        "tmdb_id": 680,
        "media_type": MediaType.MOVIE,
        "title": "Pulp Fiction",
        "overview": "The lives of two mob hitmen, a boxer, a gangster and his wife intertwine.",
        "release_date": date(1994, 10, 14),
        "runtime": 154,
        "genres": ["Thriller", "Crime"],
        "original_language": "en",
        "popularity": 78.5,
        "vote_average": 8.5,
        "vote_count": 27000
    }
]

SEED_TV_SHOWS = [
    {
        "tmdb_id": 1396,
        "media_type": MediaType.TV,
        "title": "Breaking Bad",
        "overview": "A chemistry teacher diagnosed with cancer turns to cooking meth.",
        "release_date": date(2008, 1, 20),
        "number_of_seasons": 5,
        "number_of_episodes": 62,
        "episode_run_time": [45, 47],
        "genres": ["Drama", "Crime", "Thriller"],
        "original_language": "en",
        "popularity": 95.3,
        "vote_average": 9.0,
        "vote_count": 13000
    },
    {
        "tmdb_id": 1399,
        "media_type": MediaType.TV,
        "title": "Game of Thrones",
        "overview": "Nine noble families fight for control of the lands of Westeros.",
        "release_date": date(2011, 4, 17),
        "number_of_seasons": 8,
        "number_of_episodes": 73,
        "episode_run_time": [50, 60],
        "genres": ["Drama", "Fantasy", "Adventure"],
        "original_language": "en",
        "popularity": 88.7,
        "vote_average": 8.3,
        "vote_count": 22000
    }
]


async def seed_database():
    """Seed the database with initial data"""
    
    # Safety check
    if not is_safe_environment():
        print("❌ ERROR: Seeding blocked - not in dev/test environment")
        print("   Current env:", os.getenv("ENVIRONMENT", "production"))
        print("   DB URL:", os.getenv("DATABASE_URL", "")[:30] + "...")
        return False
    
    print("✅ Safe environment detected - proceeding with seeding...")
    
    async with async_session_maker() as session:
        try:
            # Check if already seeded
            result = await session.execute(select(User).limit(1))
            if result.first():
                print("⚠️  Database already contains data - skipping seed")
                return True
            
            print("\n📝 Seeding users...")
            users = []
            for user_data in SEED_USERS:
                password = user_data.pop("password")
                user = User(
                    **user_data,
                    hashed_password=get_password_hash(password),
                    id=uuid4()
                )
                session.add(user)
                users.append(user)
            
            await session.commit()
            print(f"   ✓ Created {len(users)} users")
            
            # Refresh to get IDs
            for user in users:
                await session.refresh(user)
            
            print("\n🎬 Seeding movies...")
            movies = []
            for movie_data in SEED_MOVIES:
                media = Media(**movie_data, id=uuid4())
                session.add(media)
                movies.append(media)
            
            print("\n📺 Seeding TV shows...")
            tv_shows = []
            for tv_data in SEED_TV_SHOWS:
                media = Media(**tv_data, id=uuid4())
                session.add(media)
                tv_shows.append(media)
            
            await session.commit()
            all_media = movies + tv_shows
            print(f"   ✓ Created {len(all_media)} media items")
            
            # Refresh media
            for media in all_media:
                await session.refresh(media)
            
            print("\n📚 Creating user media entries...")
            # User 1 (john) watches Fight Club
            entry1 = UserMediaEntry(
                user_id=users[1].id,
                media_id=movies[0].id,
                list_status=ListStatus.COMPLETED,
                score=9,
                is_favorite=True,
                completed_at=datetime.utcnow() - timedelta(days=5)
            )
            session.add(entry1)
            
            # User 1 watching Breaking Bad
            entry2 = UserMediaEntry(
                user_id=users[1].id,
                media_id=tv_shows[0].id,
                list_status=ListStatus.WATCHING,
                current_season=3,
                current_episode=5,
                score=10,
                started_at=datetime.utcnow() - timedelta(days=30)
            )
            session.add(entry2)
            
            # User 2 (jane) plan to watch Godfather
            entry3 = UserMediaEntry(
                user_id=users[2].id,
                media_id=movies[1].id,
                list_status=ListStatus.PLAN_TO_WATCH
            )
            session.add(entry3)
            
            await session.commit()
            print("   ✓ Created 3 user media entries")
            
            print("\n⭐ Creating reviews...")
            review1 = Review(
                user_id=users[1].id,
                media_id=movies[0].id,
                content="An absolute masterpiece! The twist at the end blew my mind.",
                rating=5
            )
            session.add(review1)
            
            review2 = Review(
                user_id=users[3].id,
                media_id=movies[1].id,
                content="The greatest film ever made. Marlon Brando is incredible.",
                rating=5
            )
            session.add(review2)
            
            await session.commit()
            print("   ✓ Created 2 reviews")
            
            print("\n💭 Creating private comments...")
            comment = Comment(
                user_id=users[1].id,
                media_id=tv_shows[0].id,
                content="Note to self: rewatch the train episode"
            )
            session.add(comment)
            await session.commit()
            print("   ✓ Created 1 comment")
            
            print("\n👥 Creating friendships...")
            friendship1 = Friendship(
                user_one_id=users[1].id,
                user_two_id=users[2].id,
                status=FriendshipStatus.ACCEPTED
            )
            session.add(friendship1)
            
            friendship2 = Friendship(
                user_one_id=users[1].id,
                user_two_id=users[3].id,
                status=FriendshipStatus.PENDING
            )
            session.add(friendship2)
            
            await session.commit()
            print("   ✓ Created 2 friendships")
            
            print("\n🏆 Creating challenge group...")
            challenge = Group(
                name="Star Wars Marathon",
                description="Watch all Star Wars films in chronological order",
                group_type=GroupType.PUBLIC_COMMUNITY,
                creator_id=users[0].id,
                is_challenge=True,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                media_list=[11, 1891, 1892, 1893, 1894, 1895]  # Star Wars TMDB IDs
            )
            session.add(challenge)
            await session.commit()
            await session.refresh(challenge)
            
            membership = GroupMembership(
                user_id=users[1].id,
                group_id=challenge.id,
                is_admin=False
            )
            session.add(membership)
            await session.commit()
            print("   ✓ Created 1 challenge group")
            
            print("\n📊 Creating activities...")
            activity1 = Activity(
                user_id=users[1].id,
                activity_type=ActivityType.MEDIA_COMPLETED,
                details={"media_id": str(movies[0].id), "title": "Fight Club"}
            )
            session.add(activity1)
            
            activity2 = Activity(
                user_id=users[1].id,
                activity_type=ActivityType.REVIEW_POSTED,
                details={"media_id": str(movies[0].id), "rating": 5}
            )
            session.add(activity2)
            
            await session.commit()
            print("   ✓ Created 2 activities")
            
            print("\n✅ Database seeded successfully!")
            print("\n📋 Seed Summary:")
            print(f"   • Users: {len(users)}")
            print(f"   • Movies: {len(movies)}")
            print(f"   • TV Shows: {len(tv_shows)}")
            print(f"   • User Entries: 3")
            print(f"   • Reviews: 2")
            print(f"   • Comments: 1")
            print(f"   • Friendships: 2")
            print(f"   • Groups: 1")
            print(f"   • Activities: 2")
            print("\n🔐 Test Credentials:")
            print("   Admin: admin@omnilog.com / Admin123!")
            print("   User:  john@example.com / User123!")
            
            return True
            
        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error seeding database: {e}")
            import traceback
            traceback.print_exc()
            return False


async def clear_database():
    """Clear all data from database (DEV/TEST ONLY)"""
    
    if not is_safe_environment():
        print("❌ ERROR: Clear blocked - not in dev/test environment")
        return False
    
    print("⚠️  WARNING: This will delete ALL data!")
    confirm = input("Type 'DELETE ALL' to confirm: ")
    
    if confirm != "DELETE ALL":
        print("❌ Cancelled")
        return False
    
    async with async_session_maker() as session:
        try:
            from app.db.models import SQLModel
            from app.db.session import engine
            
            async with engine.begin() as conn:
                await conn.run_sync(SQLModel.metadata.drop_all)
                await conn.run_sync(SQLModel.metadata.create_all)
            
            print("✅ Database cleared successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error clearing database: {e}")
            return False


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        asyncio.run(clear_database())
    else:
        asyncio.run(seed_database())