"""
Cloudflare R2 Storage Service for profile pictures and challenge avatars
Uses S3-compatible API
"""
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from typing import Optional
from uuid import UUID
import hashlib
from datetime import datetime

from app.core.config import settings


class R2StorageService:
    """Service for handling file uploads to Cloudflare R2"""
    
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    
    def __init__(self):
        self._client = None
    
    @property
    def client(self):
        """Lazy initialization of S3 client"""
        if self._client is None:
            self._client = boto3.client(
                's3',
                endpoint_url=settings.R2_ENDPOINT_URL,
                aws_access_key_id=settings.R2_ACCESS_KEY_ID,
                aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
                config=Config(
                    signature_version='s3v4',
                    retries={'max_attempts': 3}
                ),
                region_name='auto'
            )
        return self._client
    
    def _generate_filename(self, folder: str, entity_id: UUID, original_filename: str) -> str:
        """Generate unique filename for avatar"""
        ext = original_filename.rsplit('.', 1)[-1].lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
        hash_input = f"{entity_id}{timestamp}".encode()
        file_hash = hashlib.md5(hash_input).hexdigest()[:8]
        return f"{folder}/{entity_id}/{file_hash}.{ext}"
    
    def validate_file(self, filename: str, file_size: int) -> tuple[bool, str]:
        """Validate file extension and size"""
        if '.' not in filename:
            return False, "Invalid filename"
        
        ext = filename.rsplit('.', 1)[-1].lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            return False, f"File type not allowed. Allowed: {', '.join(self.ALLOWED_EXTENSIONS)}"
        
        if file_size > self.MAX_FILE_SIZE:
            return False, f"File too large. Max size: {self.MAX_FILE_SIZE // (1024*1024)}MB"
        
        return True, "OK"
    
    async def _upload_file(
        self,
        folder: str,
        entity_id: UUID,
        file_content: bytes,
        original_filename: str,
        content_type: str
    ) -> tuple[bool, str]:
        """
        Generic upload method
        
        Returns:
            tuple: (success, url_or_error_message)
        """
        try:
            # Validate
            is_valid, message = self.validate_file(original_filename, len(file_content))
            if not is_valid:
                return False, message
            
            # Generate filename
            key = self._generate_filename(folder, entity_id, original_filename)
            
            # Upload to R2
            self.client.put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=key,
                Body=file_content,
                ContentType=content_type,
                CacheControl='public, max-age=31536000'  # 1 year cache
            )
            
            # Return public URL
            public_url = f"{settings.R2_PUBLIC_URL}/{key}"
            return True, public_url
            
        except ClientError as e:
            return False, f"Upload failed: {str(e)}"
        except Exception as e:
            return False, f"Unexpected error: {str(e)}"
    
    async def upload_avatar(
        self,
        user_id: UUID,
        file_content: bytes,
        original_filename: str,
        content_type: str
    ) -> tuple[bool, str]:
        """Upload user avatar to R2"""
        return await self._upload_file(
            folder="avatars",
            entity_id=user_id,
            file_content=file_content,
            original_filename=original_filename,
            content_type=content_type
        )
    
    async def upload_challenge_avatar(
        self,
        challenge_id: UUID,
        file_content: bytes,
        original_filename: str,
        content_type: str
    ) -> tuple[bool, str]:
        """Upload challenge avatar to R2"""
        return await self._upload_file(
            folder="challenges",
            entity_id=challenge_id,
            file_content=file_content,
            original_filename=original_filename,
            content_type=content_type
        )
    
    async def delete_avatar(self, avatar_url: str) -> bool:
        """Delete avatar from R2 (works for both user and challenge avatars)"""
        try:
            if not avatar_url or settings.R2_PUBLIC_URL not in avatar_url:
                return True  # Not an R2 URL, nothing to delete
            
            # Extract key from URL
            key = avatar_url.replace(f"{settings.R2_PUBLIC_URL}/", "")
            
            self.client.delete_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=key
            )
            return True
            
        except ClientError:
            return False
        except Exception:
            return False


# Singleton instance
r2_storage = R2StorageService()