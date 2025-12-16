from typing import Dict, List, Any, Optional
from collections import Counter
from datetime import datetime
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.db.models import Media, UserMediaEntry, ListStatus, MediaType, Genre
from app.crud import crud_media
from app.services.tmdb_service import tmdb_service
from app.schemas.media import MediaRead
from app.schemas.genre import GenreRead


class RecommendationService:
    """
    Service de recommandation basé sur l'analyse du profil utilisateur.
    N'utilise TMDB que comme source de données, pas comme moteur de recommandation.
    """

    def __init__(self):
        self.weights = {
            "genre_match": 0.40,  # 40% du score
            "cast_match": 0.20,  # 20% du score
            "director_match": 0.15,  # 15% du score
            "rating_proximity": 0.15,  # 15% du score
            "popularity_boost": 0.10  # 10% du score
        }

    async def build_user_profile(
            self,
            session: AsyncSession,
            user_id: UUID,
            min_score: float = 4.0,
            limit: int = 20
    ) -> Dict[str, Any]:
        """
        Construit le profil de préférences d'un utilisateur basé sur ses médias aimés.

        Returns:
            {
                "genres": Counter({18: 5, 28: 3, ...}),
                "actors": Counter({"Tom Hanks": 3, ...}),
                "directors": Counter({"Nolan": 2, ...}),
                "avg_rating": 7.8,
                "year_range": (2015, 2024),
                "avg_popularity": 150.0,
                "preferred_runtime": (90, 140),
                "media_count": 15
            }
        """

        # 1. Récupérer les médias très bien notés (score >= 8.0)
        liked_entries = await crud_media.get_top_rated_completed(
            session=session,
            user_id=user_id,
            min_score=min_score,
            limit=limit
        )
        if not liked_entries:
            return None

        # 2. Initialiser les compteurs
        genre_counter = Counter()
        actor_counter = Counter()
        director_counter = Counter()
        ratings = []
        years = []
        popularities = []
        runtimes = []

        # 3. Analyser chaque média aimé
        for entry in liked_entries:
            media = await crud_media.get_media_by_id(session, entry.media_id)
            if not media:
                continue

            # Genres
            if media.genre_ids:
                for genre_id in media.genre_ids:
                    genre_counter[genre_id] += 1

            # Acteurs
            if media.actors:
                for actor in media.actors[:5]:  # Top 5 acteurs seulement
                    actor_counter[actor] += 1

            # Réalisateurs
            if media.directors:
                for director in media.directors:
                    director_counter[director] += 1

            # Statistiques numériques
            if media.vote_average:
                ratings.append(media.vote_average)
            if media.release_date:
                years.append(media.release_date.year)
            if media.popularity:
                popularities.append(media.popularity)
            if media.runtime:
                runtimes.append(media.runtime)

        # 4. Calculer les moyennes et ranges
        avg_rating = sum(ratings) / len(ratings) if ratings else 7.0
        avg_popularity = sum(popularities) / len(popularities) if popularities else 50.0

        year_range = (min(years), max(years)) if years else (2010, 2024)
        runtime_range = (
            int(sum(runtimes) / len(runtimes) * 0.8),  # -20%
            int(sum(runtimes) / len(runtimes) * 1.2)  # +20%
        ) if runtimes else (80, 150)

        return {
            "genres": genre_counter,
            "actors": actor_counter,
            "directors": director_counter,
            "avg_rating": avg_rating,
            "year_range": year_range,
            "avg_popularity": avg_popularity,
            "preferred_runtime": runtime_range,
            "media_count": len(liked_entries)
        }

    def calculate_match_score(
            self,
            media_data: Dict[str, Any],
            user_profile: Dict[str, Any]
    ) -> float:
        """
        Calcule le score de correspondance entre un média et le profil utilisateur.

        Returns:
            Score entre 0.0 et 1.0
        """
        score = 0.0

        # 1. GENRE MATCH (40%)
        genre_ids = media_data.get("genre_ids", [])
        if genre_ids and user_profile["genres"]:
            total_genre_weight = sum(user_profile["genres"].values())
            genre_score = sum(
                user_profile["genres"].get(gid, 0) for gid in genre_ids
            ) / total_genre_weight
            score += genre_score * self.weights["genre_match"]

        # 2. CAST MATCH (20%)
        actors = media_data.get("actors", [])
        if actors and user_profile["actors"]:
            total_actor_weight = sum(user_profile["actors"].values())
            actor_score = sum(
                user_profile["actors"].get(actor, 0) for actor in actors[:5]
            ) / max(total_actor_weight, 1)
            score += actor_score * self.weights["cast_match"]

        # 3. DIRECTOR MATCH (15%)
        directors = media_data.get("directors", [])
        if directors and user_profile["directors"]:
            total_director_weight = sum(user_profile["directors"].values())
            director_score = sum(
                user_profile["directors"].get(director, 0) for director in directors
            ) / max(total_director_weight, 1)
            score += director_score * self.weights["director_match"]

        # 4. RATING PROXIMITY (15%)
        vote_avg = media_data.get("vote_average", 5.0)
        rating_diff = abs(vote_avg - user_profile["avg_rating"])
        rating_score = max(0, 1 - (rating_diff / 10))
        score += rating_score * self.weights["rating_proximity"]

        # 5. POPULARITY BOOST (10%)
        popularity = media_data.get("popularity", 0)
        popularity_score = min(popularity / user_profile["avg_popularity"], 1.5) / 1.5
        score += popularity_score * self.weights["popularity_boost"]

        return min(score, 1.0)

    async def get_recommendations(
            self,
            session: AsyncSession,
            user_id: UUID,
            limit: int = 30
    ) -> List[MediaRead]:
        """
        Génère des recommandations personnalisées pour un utilisateur.
        """

        # 1. Construire le profil utilisateur
        user_profile = await self.build_user_profile(session, user_id)

        if not user_profile:
            # Top rated TMDB si pas assez de données
            return await self._get_fallback_recommendations(session, user_id, limit)

        # 2. Récupérer les média terminer de l'utilisateur
        full_library = await crud_media.get_user_library(
            session=session,
            user_id=user_id,
            limit=1000,
            status=ListStatus.COMPLETED
        )



        library_tmdb_map: Dict[int, ListStatus] = {}
        for entry in full_library:
            media = await crud_media.get_media_by_id(session, entry.media_id)
            if media:
                library_tmdb_map[media.tmdb_id] = entry.list_status

        # 3. Récupérer les candidats depuis TMDB via Discover
        candidates = await self._fetch_tmdb_candidates(user_profile)

        # 4. Scorer chaque candidat
        scored_candidates = []
        print(f"Candidates; {candidates}")
        for candidate in candidates:
            tmdb_id = candidate.get("id")
            # Exclure si déjà dans la bibliothèque
            if tmdb_id in library_tmdb_map:

                continue

            match_score = self.calculate_match_score(candidate, user_profile)

            scored_candidates.append({
                "data": candidate,
                "score": match_score,
                "vote_average": candidate.get("vote_average", 0),
                "in_library": False,
                "library_status": None
            })

        # 5. Trier par score de match (desc) puis vote_average (desc)
        scored_candidates.sort(
            key=lambda x: (-x["score"], -x["vote_average"])
        )

        # 6. Convertir en MediaRead
        final_results = []
        for candidate in scored_candidates[:limit]:
            item_data = candidate["data"]

            # Déterminer le type de média
            if "title" in item_data:
                m_type = MediaType.MOVIE
            elif "name" in item_data:
                m_type = MediaType.TV
            else:
                continue

            # Récupérer les genres
            genre_objects = []
            if "genre_ids" in item_data:
                genre_ids = item_data["genre_ids"]
                stmt = select(Genre).where(
                    Genre.id.in_(genre_ids),
                    Genre.media_type == m_type
                )
                result = await session.execute(stmt)
                genre_objects = result.scalars().all()

            # Mapper vers MediaRead
            media_read = self._map_tmdb_to_schema(item_data, m_type, genre_objects)
            media_read.in_library = False
            media_read.library_status = None

            final_results.append(media_read)

        return final_results

    async def _fetch_tmdb_candidates(
            self,
            user_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Récupère les candidats depuis TMDB Discover API basé sur le profil.
        """
        candidates = []

        # Top 3 genres préférés
        top_genres = [
            str(genre_id)
            for genre_id, _ in user_profile["genres"].most_common(3)
        ]
        genre_string = ",".join(top_genres) if top_genres else None

        # Plage d'années
        year_min, year_max = user_profile["year_range"]

        # Note minimale (légèrement en dessous de la moyenne user)
        min_rating = max(user_profile["avg_rating"] - 1.5, 3.0)

        # Découverte films
        try:
            movie_results = await tmdb_service.discover_movies(
                with_genres=genre_string,
                primary_release_year_gte=year_min,
                primary_release_year_lte=year_max,
                vote_average_gte=min_rating,
                sort_by="vote_average.desc",
                page=1
            )
            candidates.extend(movie_results.get("results", []))
        except Exception as e:
            print(f"❌ Error fetching movie candidates: {e}")

        # Découverte séries
        try:
            tv_results = await tmdb_service.discover_tv(
                with_genres=genre_string,
                first_air_date_year_gte=year_min,
                first_air_date_year_lte=year_max,
                vote_average_gte=min_rating,
                sort_by="vote_average.desc",
                page=1
            )
            candidates.extend(tv_results.get("results", []))
        except Exception as e:
            print(f"❌ Error fetching TV candidates: {e}")

        return candidates

    async def _get_fallback_recommendations(
            self,
            session: AsyncSession,
            user_id: UUID,
            limit: int
    ) -> List[MediaRead]:
        """
        Recommandations de secours si l'utilisateur n'a pas assez de données.
        Utilise simplement les top rated de TMDB.
        """
        full_library = await crud_media.get_user_library(
            session=session,
            user_id=user_id,
            limit=1000
        )

        library_tmdb_map = {}
        for entry in full_library:
            media = await crud_media.get_media_by_id(session, entry.media_id)
            if media:
                library_tmdb_map[media.tmdb_id] = entry.list_status

        tmdb_results = await tmdb_service.get_top_rated_movies(page=1)
        results = []

        for item in tmdb_results.get("results", []):
            tmdb_id = item["id"]
            media_read = self._map_tmdb_to_schema(item, MediaType.MOVIE)

            if tmdb_id in library_tmdb_map:
                media_read.in_library = True
                media_read.library_status = library_tmdb_map[tmdb_id]
            else:
                results.append(media_read)

        return results[:limit]

    def _map_tmdb_to_schema(
            self,
            item: Dict[str, Any],
            media_type: MediaType,
            genres: Optional[List[Genre]] = None
    ) -> MediaRead:
        """
        Convertit un résultat TMDB en MediaRead.
        """
        genre_reads = [
            GenreRead(id=g.id, media_type=g.media_type, name=g.name)
            for g in (genres or [])
        ]

        return MediaRead(
            id=None,
            tmdb_id=item["id"],
            media_type=media_type,
            title=item.get("title") or item.get("name", ""),
            original_title=item.get("original_title") or item.get("original_name"),
            overview=item.get("overview"),
            poster_path=item.get("poster_path"),
            backdrop_path=item.get("backdrop_path"),
            release_date=item.get("release_date") or item.get("first_air_date"),
            genre_ids=item.get("genre_ids", []),
            genres=genre_reads,
            vote_average=item.get("vote_average"),
            vote_count=item.get("vote_count"),
            popularity=item.get("popularity"),
            original_language=item.get("original_language"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            in_library=False,
            library_status=None
        )


# Instance globale
recommendation_service = RecommendationService()