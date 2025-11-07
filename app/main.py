from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api.router import api_router
from app.db.session import init_db
from app.services.redis_service import redis_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    print("🚀 Starting up Omnilog API...")
    
    await init_db()
    print("✅ Database initialized")
    
    await redis_service.connect()
    print("✅ Redis connected")
    
    yield
    
    print("🔴 Shutting down Omnilog API...")
    await redis_service.disconnect()
    print("✅ Redis disconnected")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Media tracking API for movies and TV shows",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Welcome to Omnilog API",
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": settings.VERSION
    }
