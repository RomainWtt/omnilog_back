from pydantic import BaseModel


class WatchlistStats(BaseModel):
    """Statistiques de la watchlist de l'utilisateur"""
    total: int
    movies: int
    series: int
    anime: int

    class Config:
        from_attributes = True
