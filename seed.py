"""
Database seeding script for Omnilog backend (SIMPLIFIED)
SAFE FOR PRODUCTION - only runs in dev/test environments
"""
import asyncio
import os
from datetime import datetime, date, timezone
from uuid import uuid4
from dotenv import load_dotenv
from sqlmodel import select

load_dotenv()

from app.db.session import async_session_maker, engine
from app.db.models import SQLModel, User, MediaType, Genre
from app.core.security import get_password_hash


def is_safe_environment() -> bool:
    env = os.getenv("ENVIRONMENT", "production").lower()
    db_url = os.getenv("DATABASE_URL", "")
    if env == "production" or "prod" in db_url.lower():
        return False
    return env in ["development", "dev", "test", "testing", "local"]


def utc_now() -> datetime:
    """Return current UTC time as timezone-naive datetime for database storage"""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# Genre colors mapping
GENRE_COLORS = {
    "Action": "#FF4444",
    "Adventure": "#FF8C00",
    "Animation": "#9370DB",
    "Comedy": "#FFD700",
    "Crime": "#8B0000",
    "Documentary": "#708090",
    "Drama": "#4682B4",
    "Family": "#32CD32",
    "Fantasy": "#9932CC",
    "History": "#8B4513",
    "Horror": "#000000",
    "Music": "#FF1493",
    "Mystery": "#483D8B",
    "Romance": "#FF69B4",
    "Science Fiction": "#00CED1",
    "TV Movie": "#696969",
    "Thriller": "#DC143C",
    "War": "#556B2F",
    "Western": "#D2691E",
    "Action & Adventure": "#FF6347",
    "Kids": "#87CEEB",
    "News": "#4169E1",
    "Reality": "#FFA500",
    "Sci-Fi & Fantasy": "#1E90FF",
    "Soap": "#FFB6C1",
    "Talk": "#20B2AA",
    "War & Politics": "#8B4513"
}

TMDB_MOVIE_GENRES = [
    {"id": 28, "name": "Action"},
    {"id": 12, "name": "Adventure"},
    {"id": 16, "name": "Animation"},
    {"id": 35, "name": "Comedy"},
    {"id": 80, "name": "Crime"},
    {"id": 99, "name": "Documentary"},
    {"id": 18, "name": "Drama"},
    {"id": 10751, "name": "Family"},
    {"id": 14, "name": "Fantasy"},
    {"id": 36, "name": "History"},
    {"id": 27, "name": "Horror"},
    {"id": 10402, "name": "Music"},
    {"id": 9648, "name": "Mystery"},
    {"id": 10749, "name": "Romance"},
    {"id": 878, "name": "Science Fiction"},
    {"id": 10770, "name": "TV Movie"},
    {"id": 53, "name": "Thriller"},
    {"id": 10752, "name": "War"},
    {"id": 37, "name": "Western"}
]

TMDB_TV_GENRES = [
    {"id": 10759, "name": "Action & Adventure"},
    {"id": 16, "name": "Animation"},
    {"id": 35, "name": "Comedy"},
    {"id": 80, "name": "Crime"},
    {"id": 99, "name": "Documentary"},
    {"id": 18, "name": "Drama"},
    {"id": 10751, "name": "Family"},
    {"id": 10762, "name": "Kids"},
    {"id": 9648, "name": "Mystery"},
    {"id": 10763, "name": "News"},
    {"id": 10764, "name": "Reality"},
    {"id": 10765, "name": "Sci-Fi & Fantasy"},
    {"id": 10766, "name": "Soap"},
    {"id": 10767, "name": "Talk"},
    {"id": 10768, "name": "War & Politics"},
    {"id": 37, "name": "Western"}
]

SEED_USERS = [
    {
        "username": "admin",
        "email": "admin@omnilog.com",
        "password": "Admin123!",
        "is_admin": True,
        "is_public": True,
        "email_verified": True,
        "birth_date": date(1990, 1, 1),
        "avatar_url": "https://i.pravatar.cc/150?img=1"
    },
    {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "User123!",
        "is_public": True,
        "email_verified": True,
        "birth_date": date(1995, 6, 15),
        "avatar_url": "https://i.pravatar.cc/150?img=2"
    },
    {
        "username": "jane_smith",
        "email": "jane@example.com",
        "password": "User123!",
        "is_public": True,
        "email_verified": True,
        "birth_date": date(1992, 3, 20),
        "avatar_url": "https://i.pravatar.cc/150?img=3"
    },
    {
        "username": "bob_wilson",
        "email": "bob@example.com",
        "password": "User123!",
        "is_public": True,
        "email_verified": False,
        "birth_date": date(1998, 11, 8),
        "avatar_url": "https://i.pravatar.cc/150?img=4"
    }
]


async def init_db():
    """Create all tables"""
    print("🔧 Initializing database schema...")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    print("   ✓ Tables created")


async def seed_database():
    if not is_safe_environment():
        print("❌ ERROR: Not in dev/test environment")
        return False

    print("✅ Safe environment detected")

    # Initialize database schema first
    await init_db()

    async with async_session_maker() as session:
        try:
            # Check if already seeded
            result = await session.execute(select(User).limit(1))
            if result.first():
                print("⚠️  Database already contains users - skipping seed")
                return True

            # 1. Seed genres with colors
            print("\n🎭 Seeding genres...")
            for genre_data in TMDB_MOVIE_GENRES:
                genre = Genre(
                    id=genre_data["id"],
                    media_type=MediaType.MOVIE,
                    name=genre_data["name"],
                    color=GENRE_COLORS.get(genre_data["name"], "#808080")
                )
                session.add(genre)

            for genre_data in TMDB_TV_GENRES:
                genre = Genre(
                    id=genre_data["id"],
                    media_type=MediaType.TV,
                    name=genre_data["name"],
                    color=GENRE_COLORS.get(genre_data["name"], "#808080")
                )
                session.add(genre)

            await session.commit()
            print(f"   ✓ {len(TMDB_MOVIE_GENRES)} movie + {len(TMDB_TV_GENRES)} TV genres with colors")

            # 2. Seed users
            print("\n👥 Seeding users...")
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
            for user in users:
                await session.refresh(user)
            print(f"   ✓ {len(users)} users")

            print("\n✅ Seed complete!")
            print("\n📋 Summary:")
            print(f"   • Genres: {len(TMDB_MOVIE_GENRES) + len(TMDB_TV_GENRES)} (with colors)")
            print(f"   • Users: {len(users)} (with avatars)")
            print("\n🔐 Test Credentials:")
            print("   admin@omnilog.com / Admin123! (admin, verified)")
            print("   john@example.com / User123! (verified)")
            print("   jane@example.com / User123! (verified)")
            print("   bob@example.com / User123! (not verified)")
            print("\n💡 Tip: Media data will be populated via TMDB API during usage")

            return True

        except Exception as e:
            await session.rollback()
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False


async def clear_database():
    """Clear all data (DEV/TEST ONLY)"""

    if not is_safe_environment():
        print("❌ ERROR: Not in dev/test environment")
        return False

    print("⚠️  WARNING: This will delete ALL data!")
    confirm = input("Type 'DELETE ALL' to confirm: ")

    if confirm != "DELETE ALL":
        print("❌ Cancelled")
        return False

    try:
        print("🗑️  Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.drop_all)
        print("✅ Database cleared")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        asyncio.run(clear_database())
    else:
        asyncio.run(seed_database())