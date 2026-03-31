"""Run once: python -m backend.scripts.init_db"""
from backend.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.models.permission import Permission
from backend.services.auth_service import hash_password
from backend.config import settings
import backend.models  # ensure models are registered

RESOURCE_LIST = ["system", "services", "files", "scripts", "crontab", "logs", "network"]

DEFAULT_PERMISSIONS = {
    UserRole.admin: [(r, a) for r in RESOURCE_LIST for a in ("read", "write", "execute")],
    UserRole.operator: (
        [(r, "read") for r in RESOURCE_LIST]
        + [("services", "write"), ("services", "execute"),
           ("scripts", "write"), ("scripts", "execute"),
           ("crontab", "write"), ("crontab", "execute"),
           ("files", "write")]
    ),
    UserRole.readonly: [(r, "read") for r in RESOURCE_LIST],
}

def seed_permissions(db):
    if db.query(Permission).first() is not None:
        return
    for role, pairs in DEFAULT_PERMISSIONS.items():
        for resource, action in pairs:
            db.add(Permission(role=role, resource=resource, action=action))
    db.commit()

def init():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    existing = db.query(User).filter_by(username=settings.admin_username).first()
    if not existing:
        admin = User(
            username=settings.admin_username,
            hashed_password=hash_password(settings.admin_password),
            role=UserRole.admin,
        )
        db.add(admin)
        db.commit()
        print(f"Admin user '{settings.admin_username}' created.")
    else:
        print(f"Admin user '{settings.admin_username}' already exists.")
    seed_permissions(db)
    db.close()

if __name__ == "__main__":
    init()
