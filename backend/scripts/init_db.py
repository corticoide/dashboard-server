"""Run once: python -m backend.scripts.init_db"""
from backend.database import engine, Base, SessionLocal
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password
from backend.config import settings
import backend.models  # ensure models are registered

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
    db.close()

if __name__ == "__main__":
    init()
