from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.models.user import User
from backend.schemas.auth import LoginRequest, TokenResponse
from backend.services.auth_service import verify_password, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Note: /refresh and /logout endpoints are deferred to Phase 2
@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    token = create_access_token(user_id=user.id, username=user.username, role=user.role.value)
    return TokenResponse(access_token=token)
