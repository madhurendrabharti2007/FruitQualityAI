"""Optional cookie-based authentication and prediction history."""
from datetime import datetime, timedelta, timezone
import os
import re
import secrets
import logging
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from app.database import Prediction, SessionLocal, User, PasswordReset
from app.schemas import AuthInput, HistoryResponse, UserResponse, VendorRequestResponse, ForgotPasswordRequest, ResetPasswordRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
SECRET_KEY = os.getenv("JWT_SECRET", "change-this-development-secret")
ALGORITHM = "HS256"
TOKEN_DAYS = 7


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        return int(user_id) if user_id else None
    except (JWTError, TypeError, ValueError):
        return None


def current_user(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)) -> User:
    user_id = decode_token(access_token or "")
    user = db.get(User, user_id) if user_id else None
    if not user:
        raise HTTPException(401, "Please sign in to continue.")
    return user


def user_payload(user: User) -> dict:
    return {"id": user.id, "name": user.name, "email": user.email, "created_at": user.created_at.isoformat(), "role": user.role or "customer"}


def set_token(response: Response, user: User) -> None:
    token = jwt.encode({"sub": str(user.id), "exp": datetime.now(timezone.utc) + timedelta(days=TOKEN_DAYS)}, SECRET_KEY, algorithm=ALGORITHM)
    response.set_cookie("access_token", token, httponly=True, samesite="lax", secure=False, max_age=TOKEN_DAYS * 86400)

@router.post("/signup", response_model=UserResponse)
def signup(payload: AuthInput, response: Response, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise HTTPException(422, "Enter a valid email address.")
    if not payload.name:
        raise HTTPException(422, "Name is required.")
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(409, "An account with that email already exists.")
    user = User(name=payload.name.strip(), email=email, hashed_password=pwd_context.hash(payload.password), role="customer")
    db.add(user)
    db.commit()
    db.refresh(user)
    set_token(response, user)
    return user_payload(user)

@router.post("/login", response_model=UserResponse)
def login(payload: AuthInput, response: Response, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.strip().lower()).first()
    if not user or not pwd_context.verify(payload.password, user.hashed_password):
        raise HTTPException(401, "Email or password is incorrect.")
    set_token(response, user)
    return user_payload(user)

@router.post("/logout")
def logout(response: Response):
    response.delete_cookie("access_token")
    return {"status": "ok"}

@router.get("/me", response_model=UserResponse | None)
def me(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    user_id = decode_token(access_token or "")
    user = db.get(User, user_id) if user_id else None
    return user_payload(user) if user else None

@router.get("/history", response_model=list[HistoryResponse])
def history(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    user = current_user(access_token, db)
    records = db.query(Prediction).filter(Prediction.user_id == user.id).order_by(Prediction.created_at.desc()).all()
    return [{"id": item.id, "fruit": item.fruit, "status": item.status, "confidence": item.confidence, "image_url": item.image_url, "created_at": item.created_at.isoformat(), "ripeness_stage": item.ripeness_stage, "shelf_life_estimate": item.shelf_life_estimate} for item in records]

@router.post("/request-vendor", response_model=VendorRequestResponse)
def request_vendor(access_token: str | None = Cookie(default=None), db: Session = Depends(get_db)):
    user = current_user(access_token, db)
    if user.role == "customer":
        user.role = "vendor"
        db.commit()
    return {"role": user.role, "message": "Vendor access is now active." if user.role == "vendor" else "Your account already has elevated access."}

@router.post("/forgot-password")
def forgot_password(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    """Generate a password reset token for the given email."""
    email = payload.email.strip().lower()
    user = db.query(User).filter(User.email == email).first()
    
    if not user:
        # Don't reveal whether email exists, but log it
        logger.info("Password reset requested for non-existent email: %s", email)
        return {"message": "If an account with that email exists, a reset link has been sent."}
    
    # Generate a secure random token
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=1)
    
    # Invalidate any existing unused tokens for this user
    db.query(PasswordReset).filter(PasswordReset.user_id == user.id, PasswordReset.used == False).update({"used": True})
    
    # Create new reset token
    reset = PasswordReset(user_id=user.id, token=token, expires_at=expires_at)
    db.add(reset)
    db.commit()
    
    # Production note: A real email service (e.g. SMTP or a provider like Resend/SendGrid)
    # should replace this before production.
    reset_link = f"http://localhost:5173/reset-password?token={token}"
    print("=" * 60, flush=True)
    print(f"PASSWORD RESET LINK (dev only): {reset_link}", flush=True)
    print(f"TOKEN: {token}", flush=True)
    print(f"EMAIL: {email}", flush=True)
    print(f"EXPIRES AT: {expires_at.isoformat()}", flush=True)
    print("=" * 60, flush=True)
    logger.info("=" * 60)
    logger.info("PASSWORD RESET LINK (DEV ONLY): %s", reset_link)
    logger.info("TOKEN: %s", token)
    logger.info("EMAIL: %s", email)
    logger.info("EXPIRES AT: %s", expires_at.isoformat())
    logger.info("=" * 60)
    
    return {"message": "If an account with that email exists, a reset link has been sent."}

@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    """Reset password using a valid token."""
    reset = db.query(PasswordReset).filter(
        PasswordReset.token == payload.token,
        PasswordReset.used == False
    ).first()
    
    if not reset:
        raise HTTPException(400, "Invalid or expired reset token.")
    
    if reset.expires_at < datetime.utcnow():
        reset.used = True
        db.commit()
        raise HTTPException(400, "Reset token has expired.")
    
    user = db.get(User, reset.user_id)
    if not user:
        raise HTTPException(400, "User not found.")
    
    # Update password
    user.hashed_password = pwd_context.hash(payload.new_password)
    reset.used = True
    db.commit()
    
    logger.info("Password reset successful for user: %s (email: %s)", user.id, user.email)
    
    return {"message": "Password has been reset successfully. You can now log in with your new password."}
