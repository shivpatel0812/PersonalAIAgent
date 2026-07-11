"""Authentication package."""

from app.auth.deps import AuthUser, get_current_user

__all__ = ["AuthUser", "get_current_user"]
