from fastapi import APIRouter

from app.api.endpoints import auth, users, media, library, review, report, oauth, email_verification

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(media.router, prefix="/media", tags=["media"])
api_router.include_router(library.router, prefix="/library", tags=["library"])
api_router.include_router(review.router, prefix="/review", tags=["review"])
api_router.include_router(review.router, prefix="/review_reports", tags=["report"])
api_router.include_router(oauth.router, prefix="/oauth")
api_router.include_router(email_verification.router, prefix="/email", tags=["Email Verification"])

