from backend.models.permission import Permission
from backend.models.user import UserRole


def test_seed_permissions(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perms = db_session.query(Permission).all()
    assert len(perms) > 0
    admin_perms = [p for p in perms if p.role == UserRole.admin]
    assert len(admin_perms) >= 7
    ro_perms = [p for p in perms if p.role == UserRole.readonly]
    for p in ro_perms:
        assert p.action == "read"
