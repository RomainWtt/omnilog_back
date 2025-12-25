from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from starlette.middleware.sessions import SessionMiddleware

from app.api.endpoints import websocket
from app.core.config import settings
from app.api.router import api_router
from app.db.session import init_db
from app.services.redis_service import redis_service
from fastapi.routing import APIRoute


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

#SessionMiddleware
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY,  # Même clé que JWT
    max_age=3600,
    same_site="lax",
    https_only=False  # True en production
)

# ❌ CORS - Désactivé car géré par Caddy
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=settings.CORS_ORIGINS,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# CORS - Actif uniquement en mode DEBUG (dev local sans Caddy)
if settings.DEBUG and settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    print("⚠️  CORS middleware actif (mode DEBUG)")
else:
    print("✅ CORS géré par Caddy (production)")

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

#Les websockets ne doivent pas avoir de préfix askip
app.include_router(websocket.router)

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

def use_route_names_as_operation_ids(app: FastAPI):
    for route in app.routes:
        if isinstance(route, APIRoute):
            route.operation_id = route.name

use_route_names_as_operation_ids(app)