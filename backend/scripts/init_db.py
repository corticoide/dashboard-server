"""Run once: python -m backend.scripts.init_db"""
from backend.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.models.permission import Permission
from backend.services.auth_service import hash_password
from backend.services.settings_service import seed_defaults
from backend.config import settings
import backend.models  # ensure models are registered

# Admin is NOT in this dict — admin always bypasses the Permission table.
DEFAULT_PERMISSIONS = {
    UserRole.operator: [
        ("system",      "read"),
        ("services",    "read"),  ("services",    "write"), ("services",    "execute"),
        ("files",       "read"),  ("files",       "write"),
        ("network",     "read"),
        ("scripts",     "read"),  ("scripts",     "write"), ("scripts",     "execute"),
        ("crontab",     "read"),
        ("logs",        "read"),
        ("pipelines",   "read"),  ("pipelines",   "execute"),
        ("alerts",      "read"),  ("alerts",      "write"),
        ("system_logs", "read"),
        ("processes",   "read"),  ("processes",   "execute"),
        ("disks",       "read"),  ("disks",       "write"),
    ],
    UserRole.readonly: [
        ("system",      "read"),
        ("services",    "read"),
        ("files",       "read"),
        ("network",     "read"),
        ("scripts",     "read"),
        ("crontab",     "read"),
        ("logs",        "read"),
        ("pipelines",   "read"),
        ("alerts",      "read"),
        ("system_logs", "read"),
        ("processes",   "read"),
        ("disks",       "read"),
    ],
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
    seed_defaults(db)
    db.close()

if __name__ == "__main__":
    init()
