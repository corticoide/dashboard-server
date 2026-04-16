from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict
from sqlalchemy.orm import Session
from backend.database import get_db
from backend.dependencies import require_role, _perm_cache
from backend.models.user import User, UserRole
from backend.models.permission import Permission
from backend.schemas.users import UserOut, UserCreate, UserUpdate, PermissionOut
from backend.services.auth_service import hash_password

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=List[UserOut])
def list_users(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    return db.query(User).order_by(User.id).all()


@router.post("/users", response_model=UserOut, status_code=201)
def create_user(body: UserCreate, db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    existing = db.query(User).filter(User.username == body.username).first()
    if existing:
        raise HTTPException(status_code=409, detail="Username already exists")
    try:
        role = UserRole(body.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    new_user = User(username=body.username, hashed_password=hash_password(body.password), role=role)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, db: Session = Depends(get_db), current_user=Depends(require_role("admin"))):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    if body.role is not None:
        try:
            target.role = UserRole(body.role)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid role: {body.role}")
    if body.is_active is not None:
        target.is_active = body.is_active
    if body.password is not None:
        target.hashed_password = hash_password(body.password)
    db.commit()
    db.refresh(target)
    return target


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db), current_user=Depends(require_role("admin"))):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(target)
    db.commit()
    return {"ok": True}


# ── Permissions ───────────────────────────────────────────────────────────────

@router.get("/permissions", response_model=Dict[str, List[PermissionOut]])
def list_permissions(db: Session = Depends(get_db), user=Depends(require_role("admin"))):
    result: Dict[str, List[PermissionOut]] = {}
    for role in [UserRole.operator, UserRole.readonly]:
        perms = db.query(Permission).filter(Permission.role == role).all()
        result[role.value] = [PermissionOut(resource=p.resource, action=p.action) for p in perms]
    return result


@router.put("/permissions/{role}")
def update_permissions(
    role: str,
    body: List[PermissionOut],
    db: Session = Depends(get_db),
    user=Depends(require_role("admin")),
):
    try:
        target_role = UserRole(role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {role}")
    if target_role == UserRole.admin:
        raise HTTPException(status_code=400, detail="Cannot edit admin permissions")
    db.query(Permission).filter(Permission.role == target_role).delete()
    for p in body:
        db.add(Permission(role=target_role, resource=p.resource, action=p.action))
    db.commit()
    _perm_cache.clear()
    return {"ok": True}
