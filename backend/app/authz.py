"""Role-based access dependencies for business workflows."""
from fastapi import Cookie, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import User, get_db
from app.routers.auth import current_user

ROLE_ORDER = {"guest": 0, "customer": 1, "vendor": 2, "admin": 3}


def require_role(min_role: str):
    def dependency(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
        user = current_user(access_token, db)
        if ROLE_ORDER.get(user.role or "customer", 1) < ROLE_ORDER[min_role]:
            raise HTTPException(403, f"This feature requires {min_role} access.")
        return user
    return dependency
