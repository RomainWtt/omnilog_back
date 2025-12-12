from app.db.models import MediaType, Media
from app.schemas.challenge import ChallengeProgressUpdate


async def compute_media_progress(media: Media, data: ChallengeProgressUpdate) -> dict:
    if media.media_type == MediaType.MOVIE:
        runtime = media.runtime or 1
        viewed = data.time_code or 0

        progress = int(min(viewed / runtime, 1) * 100)
        status = "completed" if progress == 100 else "watching"

        return {
            "progress": progress,
            "status": status,
            "time_code": viewed
        }

    elif media.media_type == MediaType.TV:
        total_eps = media.number_of_episodes or 1
        current_episode = data.current_episode or 0

        progress = int(min(current_episode / total_eps, 1) * 100)
        status = "completed" if progress == 100 else "watching"

        return {
            "progress": progress,
            "status": status,
            "current_season": data.current_season,
            "current_episode": current_episode
        }

    return {"progress": 0, "status": "watching"}