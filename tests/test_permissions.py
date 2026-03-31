from backend.models.permission import Permission
from backend.models.user import User, UserRole


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

def test_user_has_permission_admin(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="testadmin", hashed_password="x", role=UserRole.admin)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "execute") is True

def test_user_lacks_permission_readonly(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "execute") is False

def test_user_has_read_permission_readonly(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "read") is True
