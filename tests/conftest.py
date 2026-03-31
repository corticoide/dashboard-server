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


@pytest.fixture(autouse=True)
def reset_count_cache():
    """Clear the logs COUNT cache before each test to avoid stale counts across test DBs."""
    from backend.routers.logs import _count_cache
    _count_cache.clear()
    yield

@pytest.fixture(autouse=True)
def reset_permission_cache():
    """Clear the permission cache before each test."""
    from backend.dependencies import _perm_cache
    _perm_cache.clear()
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
    import backend.database as _db_module
    from fastapi.testclient import TestClient

    engine = create_engine("sqlite:///:memory:", **SQLITE_OPTS)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine)

    # Patch SessionLocal globally so services that call SessionLocal() directly
    # (e.g. scripts_service._flush_to_db, launch_execution) use the same
    # in-memory engine as the test client.
    import backend.services.scripts_service as _scripts_svc
    original_session_local = _db_module.SessionLocal
    original_scripts_svc_session = _scripts_svc.SessionLocal
    _db_module.SessionLocal = TestingSession
    _scripts_svc.SessionLocal = TestingSession

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
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db)
    db.close()

    yield TestClient(app, base_url="http://test")
    app.dependency_overrides.clear()
    _db_module.SessionLocal = original_session_local
    _scripts_svc.SessionLocal = original_scripts_svc_session
    Base.metadata.drop_all(engine)
