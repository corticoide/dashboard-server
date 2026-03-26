import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.database import Base
from backend.models.user import User, UserRole
from backend.services.auth_service import hash_password


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset slowapi in-memory storage before each test to avoid cross-test rate limiting."""
    from backend.limiter import limiter
    limiter._limiter.storage.reset()
    yield

SQLITE_OPTS = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool}

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:", **SQLITE_OPTS)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)

@pytest.fixture
def test_app():
    from backend.main import app
    from backend.database import get_db
    from fastapi.testclient import TestClient

    engine = create_engine("sqlite:///:memory:", **SQLITE_OPTS)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db

    db = TestingSession()
    db.add(User(username="admin", hashed_password=hash_password("adminpass"), role=UserRole.admin))
    db.commit()
    db.close()

    yield TestClient(app, base_url="http://test")
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
