from typing import List, Dict
from pydantic import BaseModel


class EpisodeSchema(BaseModel):
    episode_number: int
    name: str | None
    air_date: str | None
    runtime: int | None
    overview: str | None
    still_path: str | None
    vote_average: float | None
    vote_count: int | None
    season_number: int


class SeasonSchema(BaseModel):
    season_number: int
    episodes: List[EpisodeSchema]


class TVSeasonsSchema(BaseModel):
    seasons: Dict[int, SeasonSchema]
