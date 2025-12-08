"""
Supabase Authentication for EDoS Security Dashboard
Handles JWT verification from Supabase Auth
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer
from typing import Optional
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.database import UserProfile
from app.supabase_client import get_supabase_client

router = APIRouter()
security = HTTPBearer()


async def verify_token(token: str = Depends(security)) -> dict:
    """Verify Supabase JWT token - simplified version for development"""
    try:
        # For development: accept any Bearer token and extract user info
        # In production, use proper JWT verification

        token_str = token.credentials

        if not token_str or len(token_str) < 20:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token format"
            )

        # Try to decode JWT without verification for development
        try:
            import jwt
            import json

            # Decode without verification (for dev only)
            payload = jwt.decode(token_str, options={"verify_signature": False})

            return {
                "user_id": payload.get("sub", "dev-user-id"),
                "email": payload.get("email", "dev@example.com"),
                "role": "authenticated",
            }

        except Exception as jwt_error:
            # If JWT decode fails, create a dev user
            return {
                "user_id": "development-user-123",
                "email": "dev@example.com",
                "role": "authenticated",
            }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification failed: {str(e)}",
        )


async def get_current_user(
    token_data: dict = Depends(verify_token), db: Session = Depends(get_db)
) -> UserProfile:
    """Get current user from database using Supabase auth"""

    try:
        user_id = token_data["user_id"]
        print(f"🔐 Looking up user: {user_id}")

        # Try to find existing user profile
        user_profile = db.query(UserProfile).filter(UserProfile.id == user_id).first()

        if not user_profile:
            print(f"🔐 Creating new user profile for: {user_id}")
            # Create new user profile if doesn't exist
            user_profile = UserProfile(
                id=user_id,
                email=token_data.get("email"),
                username=token_data.get("email", "").split("@")[
                    0
                ],  # Use email prefix as username
                role="analyst",
            )
            db.add(user_profile)
            db.commit()
            db.refresh(user_profile)
            print(f"🔐 Created user profile: {user_profile.id}")

        return user_profile

    except Exception as e:
        print(f"❌ Error in get_current_user: {e}")
        import traceback

        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}",
        )


async def get_current_user_id(token_data: dict = Depends(verify_token)) -> str:
    """Get just the user ID from token (lighter than full user object)"""
    return token_data["user_id"]


async def require_role(required_roles: list):
    """Dependency factory for role-based access control"""

    def role_checker(current_user: UserProfile = Depends(get_current_user)):
        if current_user.role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Required role: {required_roles}, current role: {current_user.role}",
            )
        return current_user

    return role_checker
