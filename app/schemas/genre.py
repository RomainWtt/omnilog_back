from pydantic import BaseModel, Field
from uuid import UUID
from app.db.models import MediaType



class GenreBase(BaseModel):
    media_type: MediaType
    name: str
    color: str = Field(
        default="#808080",
        pattern="^#[0-9A-Fa-f]{6}$",  # Validation du format hexadécimal
        description="Couleur au format hexadécimal (#RRGGBB)"
    )

class GenreRead(GenreBase):
    id: int

    class Config:
        from_attributes = True