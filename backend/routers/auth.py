from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.limiter import limiter
from backend.models.user import User
from backend.schemas.auth import LoginRequest, TokenResponse
from backend.services.auth_service import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, body: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == body.username).first()
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    return TokenResponse(access_token=token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(current_user: User = Depends(get_current_user)):
    token = create_access_token(
        user_id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
    )
    return TokenResponse(access_token=token)


@router.post("/logout")
def logout():
    return {"ok": True}
