"""
Database seeding script for Omnilog backend (SIMPLIFIED)
SAFE FOR PRODUCTION - only runs in dev/test environments
"""
import asyncio
import os
from datetime import datetime, date, timedelta
from uuid import uuid4
from dotenv import load_dotenv
from sqlmodel import select

load_dotenv()

from app.db.session import async_session_maker, engine
from app.db.models import (
    SQLModel, User, Media, MediaType, Genre, UserMediaEntry, ListStatus,
    Review, Friendship, FriendshipStatus,
    Challenge, ChallengeType, ChallengeMembership, Activity, ActivityType,
    ReviewReport
)
from app.core.security import get_password_hash


def is_safe_environment() -> bool:
    env = os.getenv("ENVIRONMENT", "production").lower()
    db_url = os.getenv("DATABASE_URL", "")
    if env == "production" or "prod" in db_url.lower():
        return False
    return env in ["development", "dev", "test", "testing", "local"]


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
        "birth_date": date(1990, 1, 1)
    },
    {
        "username": "john_doe",
        "email": "john@example.com",
        "password": "User123!",
        "is_public": True,
        "birth_date": date(1995, 6, 15)
    },
    {
        "username": "jane_smith",
        "email": "jane@example.com",
        "password": "User123!",
        "is_public": False,
        "birth_date": date(1992, 3, 20)
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
            
            # 1. Seed genres
            print("\n🎭 Seeding genres...")
            for genre_data in TMDB_MOVIE_GENRES:
                genre = Genre(
                    id=genre_data["id"],
                    media_type=MediaType.MOVIE,
                    name=genre_data["name"]
                )
                session.add(genre)
            
            for genre_data in TMDB_TV_GENRES:
                genre = Genre(
                    id=genre_data["id"],
                    media_type=MediaType.TV,
                    name=genre_data["name"]
                )
                session.add(genre)
            
            await session.commit()
            print(f"   ✓ {len(TMDB_MOVIE_GENRES)} movie + {len(TMDB_TV_GENRES)} TV genres")
            
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
            
            # 3. Seed movie with genre_ids (JSON field)
            print("\n🎬 Seeding movie...")
            movie = Media(
                tmdb_id=550,
                media_type=MediaType.MOVIE,
                title="Fight Club",
                overview="Un employé insomnique crée un club de combat.",
                release_date=date(1999, 10, 15),
                runtime=139,
                genre_ids=[18, 53],  # Drama, Thriller (stored as JSON)
                actors=["Brad Pitt", "Edward Norton", "Helena Bonham Carter"],
                directors=["David Fincher"],
                original_language="fr-BE"
            )
            session.add(movie)
            await session.commit()
            await session.refresh(movie)
            print("   ✓ Movie with genres (JSON)")
            
            # 4. Seed TV show with genre_ids (JSON field)
            print("\n📺 Seeding TV show...")
            tv = Media(
                tmdb_id=1396,
                media_type=MediaType.TV,
                title="Breaking Bad",
                overview="Un prof devient dealer.",
                release_date=date(2008, 1, 20),
                number_of_seasons=5,
                number_of_episodes=62,
                genre_ids=[18, 80],  # Drama, Crime (stored as JSON)
                actors=["Bryan Cranston", "Aaron Paul", "Anna Gunn"],
                directors=["Vince Gilligan"],
                original_language="fr-BE"
            )
            session.add(tv)
            await session.commit()
            await session.refresh(tv)
            print("   ✓ TV show with genres (JSON)")
            
            # 5. User media entry
            print("\n📚 Creating user entries...")
            entry = UserMediaEntry(
                user_id=users[1].id,
                media_id=movie.id,
                list_status=ListStatus.COMPLETED,
                score=9
            )
            session.add(entry)
            await session.commit()
            print("   ✓ 1 user entry")
            
            # 6. Review
            print("\n⭐ Creating review...")
            review = Review(
                user_id=users[1].id,
                media_id=movie.id,
                content="Chef-d'œuvre absolu!",
                rating=5
            )
            session.add(review)
            await session.commit()
            await session.refresh(review)
            print("   ✓ 1 review")
            
            # 7. Review report
            print("\n🚨 Creating review report...")
            report = ReviewReport(
                reporter_id=users[2].id,
                reported_user_id=users[1].id,
                review_id=review.id,
                reason="Contenu inapproprié"
            )
            session.add(report)
            await session.commit()
            print("   ✓ 1 review report")
            
            # 8. Friendship
            print("\n👥 Creating friendship...")
            friendship = Friendship(
                user_one_id=users[1].id,
                user_two_id=users[2].id,
                status=FriendshipStatus.ACCEPTED
            )
            session.add(friendship)
            friendship2 = Friendship(
                user_one_id=users[0].id,
                user_two_id=users[1].id,
                status=FriendshipStatus.PENDING
            )
            session.add(friendship2)
            await session.commit()
            print("   ✓ 1 friendship")
            
            # 9. Challenge
            print("\n🏆 Creating challenge...")
            challenge = Challenge(
                name="Marathon Star Wars",
                description="Regarder tous les films Star Wars",
                challenge_type=ChallengeType.PUBLIC_COMMUNITY,
                creator_id=users[0].id,
                start_date=datetime.utcnow(),
                end_date=datetime.utcnow() + timedelta(days=30),
                media_list=[11, 1891, 1892, 1893, 1894, 1895]
            )
            session.add(challenge)
            await session.commit()
            await session.refresh(challenge)
            
            membership = ChallengeMembership(
                user_id=users[1].id,
                challenge_id=challenge.id,
                is_admin=False,
                progress=2,
                completed_media=[11, 1891]
            )
            session.add(membership)
            await session.commit()
            print("   ✓ 1 challenge")
            
            # 10. Activity
            print("\n📊 Creating activities...")
            activity1 = Activity(
                user_id=users[1].id,
                activity_type=ActivityType.MEDIA_COMPLETED,
                details={"media_id": str(movie.id), "title": "Fight Club"}
            )
            session.add(activity1)
            
            activity2 = Activity(
                user_id=users[1].id,
                activity_type=ActivityType.REVIEW_POSTED,
                details={"media_id": str(movie.id), "rating": 5}
            )
            session.add(activity2)
            
            await session.commit()
            print("   ✓ 2 activities")
            
            print("\n✅ Seed complete!")
            print("\n📋 Summary:")
            print(f"   • Genres: {len(TMDB_MOVIE_GENRES) + len(TMDB_TV_GENRES)}")
            print(f"   • Users: {len(users)}")
            print(f"   • Media: 2 (with genre_ids as JSON)")
            print(f"   • User entries: 1")
            print(f"   • Reviews: 1")
            print(f"   • Review reports: 1")
            print(f"   • Friendships: 1")
            print(f"   • Challenges: 1")
            print(f"   • Activities: 2")
            print("\n🔐 Test Credentials:")
            print("   admin@omnilog.com / Admin123!")
            print("   john@example.com / User123!")
            print("\n🌍 Locale: fr-BE")
            
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