from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.services.auth_service import decode_token
from backend.models.user import User, UserRole
from backend.models.permission import Permission
from backend.services.cache import TTLCache

bearer_scheme = HTTPBearer()

ROLE_HIERARCHY = {
    UserRole.readonly: 0,
    UserRole.operator: 1,
    UserRole.admin: 2,
}

_perm_cache = TTLCache()
_PERM_TTL = 60

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    try:
        payload = decode_token(credentials.credentials)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")
    return user

def require_role(minimum_role: str):
    def checker(current_user: User = Depends(get_current_user)) -> User:
        user_level = ROLE_HIERARCHY.get(current_user.role, -1)
        required_level = ROLE_HIERARCHY.get(UserRole(minimum_role), 999)
        if user_level < required_level:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return current_user
    return checker

def check_permission(db: Session, user: User, resource: str, action: str) -> bool:
    if user.role == UserRole.admin:
        return True
    cache_key = f"{user.role.value}|{resource}|{action}"
    cached = _perm_cache.get(cache_key)
    if cached is not None:
        return cached
    perm = db.query(Permission).filter(
        Permission.role == user.role,
        Permission.resource == resource,
        Permission.action == action,
    ).first()
    result = perm is not None
    _perm_cache.set(cache_key, result, _PERM_TTL)
    return result

def require_permission(resource: str, action: str):
    def checker(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
        if not check_permission(db, current_user, resource, action):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Permission denied: {resource}.{action}")
        return current_user
    return checker
