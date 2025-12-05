import os

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.email import send_verification_email
from app.db.session import get_session
from app.schemas.user import UserCreate, UserRead
from app.schemas.token import Token, LoginRequest, RefreshTokenRequest
from app.crud import crud_user
from app.core.security import create_access_token, create_refresh_token, decode_token
from datetime import datetime

from app.services.email_verification import EmailVerificationService

router = APIRouter()


@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    session: AsyncSession = Depends(get_session)
):
    """
    Register a new user account
    
    - **email**: Valid email address (must be unique)
    - **username**: Username (must be unique, 3-50 characters)
    - **password**: Password (minimum 8 characters, must contain uppercase and digit)
    - **birth_date**: Optional birth date for age verification
    """
    # Check if user already exists
    existing_user = await crud_user.get_user_by_email(session, user_data.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    existing_username = await crud_user.get_user_by_username(session, user_data.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken"
        )
    
    # Check age requirement (13+)
    if user_data.birth_date:
        today = datetime.now().date()
        age = today.year - user_data.birth_date.year - (
            (today.month, today.day) < (user_data.birth_date.month, user_data.birth_date.day)
        )
        if age < 13:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You must be at least 13 years old to register"
            )
    
    # Create user
    user = await crud_user.create_user(
        session=session,
        email=user_data.email,
        username=user_data.username,
        password=user_data.password,
        birth_date=user_data.birth_date,
        avatar_url=user_data.avatar_url
    )

    # Générer et envoyer l'email de vérification
    verification_token = EmailVerificationService.generate_token(user)
    await session.commit()
    await session.refresh(user)

    try:
        await send_verification_email(
            email=user.email,
            username=user.username,
            verification_token=verification_token,
            frontend_url=os.getenv("FRONTEND_URL", "http://localhost:5173")
        )
    except Exception as e:
        print(f"Failed to send verification email: {e}")

    return user


@router.post("/login", response_model=Token)
async def login(
    credentials: LoginRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Login with email/username and password
    
    Returns JWT access token and refresh token
    """
    user = await crud_user.authenticate_user(
        session=session,
        identifier=credentials.identifier,
        password=credentials.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username/email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    token_data: RefreshTokenRequest,
    session: AsyncSession = Depends(get_session)
):
    """
    Refresh access token using refresh token
    """
    try:
        payload = decode_token(token_data.refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        from uuid import UUID
        user = await crud_user.get_user_by_id(session, UUID(user_id))
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new tokens
        access_token = create_access_token(data={"sub": user_id})
        new_refresh_token = create_refresh_token(data={"sub": user_id})
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials"
        )
