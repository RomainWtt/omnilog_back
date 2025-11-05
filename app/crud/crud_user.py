from typing import Optional
from uuid import UUID

from sqlmodel import Session, select
from app.db.models import User
from app.schemas.user import UserCreate, UserUpdate
from app.core.security import get_password_hash


class CRUDUser:
    """
    CRUD operations for User model.
    
    This class handles all database operations related to users:
    - Creating new users
    - Reading user data (by ID, email, username)
    - Updating user information
    - Deleting users
    - Checking if users exist
    """
    
    def get(self, db: Session, user_id: UUID) -> Optional[User]:
        """
        Get a user by ID.
        
        Args:
            db: Database session
            user_id: UUID of the user
            
        Returns:
            User object if found, None otherwise
        """
        return db.get(User, user_id)
    
    def get_by_email(self, db: Session, email: str) -> Optional[User]:
        """
        Get a user by email address.
        
        Args:
            db: Database session
            email: Email address to search for
            
        Returns:
            User object if found, None otherwise
        """
        statement = select(User).where(User.email == email)
        return db.exec(statement).first()
    
    def get_by_username(self, db: Session, username: str) -> Optional[User]:
        """
        Get a user by username.
        
        Args:
            db: Database session
            username: Username to search for
            
        Returns:
            User object if found, None otherwise
        """
        statement = select(User).where(User.username == username)
        return db.exec(statement).first()
    
    def get_multi(
        self, 
        db: Session, 
        *, 
        skip: int = 0, 
        limit: int = 100
    ) -> list[User]:
        """
        Get multiple users with pagination.
        
        Args:
            db: Database session
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return
            
        Returns:
            List of User objects
        """
        statement = select(User).offset(skip).limit(limit)
        return db.exec(statement).all()
    
    def create(self, db: Session, *, obj_in: UserCreate) -> User:
        """
        Create a new user.
        
        Args:
            db: Database session
            obj_in: UserCreate schema with user data
            
        Returns:
            Created User object
        """
        db_obj = User(
            username=obj_in.username,
            email=obj_in.email,
            hashed_password=get_password_hash(obj_in.password),
            avatar_url=obj_in.avatar_url
        )
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def update(
        self, 
        db: Session, 
        *, 
        db_obj: User, 
        obj_in: UserUpdate
    ) -> User:
        """
        Update an existing user.
        
        Args:
            db: Database session
            db_obj: Existing User object from database
            obj_in: UserUpdate schema with updated data
            
        Returns:
            Updated User object
        """
        # Get the data to update, excluding unset fields
        update_data = obj_in.model_dump(exclude_unset=True)
        
        # If password is being updated, hash it
        if "password" in update_data:
            hashed_password = get_password_hash(update_data["password"])
            del update_data["password"]
            update_data["hashed_password"] = hashed_password
        
        # Update the user object
        for field, value in update_data.items():
            setattr(db_obj, field, value)
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, user_id: UUID) -> User:
        """
        Delete a user by ID.
        
        Args:
            db: Database session
            user_id: UUID of the user to delete
            
        Returns:
            Deleted User object
        """
        obj = db.get(User, user_id)
        db.delete(obj)
        db.commit()
        return obj
    
    def exists_by_email(self, db: Session, email: str) -> bool:
        """
        Check if a user with given email exists.
        
        Args:
            db: Database session
            email: Email to check
            
        Returns:
            True if user exists, False otherwise
        """
        statement = select(User).where(User.email == email)
        return db.exec(statement).first() is not None
    
    def exists_by_username(self, db: Session, username: str) -> bool:
        """
        Check if a user with given username exists.
        
        Args:
            db: Database session
            username: Username to check
            
        Returns:
            True if user exists, False otherwise
        """
        statement = select(User).where(User.username == username)
        return db.exec(statement).first() is not None
    
    def authenticate(
        self, 
        db: Session, 
        *, 
        email: str, 
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user with email and password.
        
        Args:
            db: Database session
            email: User's email
            password: Plain text password
            
        Returns:
            User object if authentication successful, None otherwise
        """
        from app.core.security import verify_password
        
        user = self.get_by_email(db, email=email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


# Create a single instance to be imported and used throughout the app
crud_user = CRUDUser()