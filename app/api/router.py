from fastapi import APIRouter
from app.api.endpoints import auth, users, media, library

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(library.router, prefix="/library", tags=["library"])