from pydantic import BaseModel, Field
from uuid import UUID
from app.db.models import MediaType



class GenreBase(BaseModel):
    media_type: MediaType
    name : str

class GenreRead(GenreBase):
    id: int

    class Config:
        from_attributes = True