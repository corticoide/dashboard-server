import pytest
from backend.models.permission import Permission
from backend.models.user import User, UserRole


def test_seed_permissions_populates_operator_and_readonly(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perms = db_session.query(Permission).all()
    assert len(perms) > 0

    roles = {p.role for p in perms}
    # Admin is NOT seeded — admin bypasses the table
    assert UserRole.admin not in roles
    assert UserRole.operator in roles
    assert UserRole.readonly in roles


def test_seed_permissions_is_idempotent(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    count_first = db_session.query(Permission).count()
    seed_permissions(db_session)  # second call — must be a no-op
    count_second = db_session.query(Permission).count()
    assert count_first == count_second


def test_readonly_only_has_read_actions(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    ro_perms = db_session.query(Permission).filter(Permission.role == UserRole.readonly).all()
    assert len(ro_perms) > 0
    for p in ro_perms:
        assert p.action == "read", f"readonly had unexpected action: {p.action} on {p.resource}"


def test_operator_has_write_on_services(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perm = db_session.query(Permission).filter(
        Permission.role == UserRole.operator,
        Permission.resource == "services",
        Permission.action == "write",
    ).first()
    assert perm is not None


def test_operator_cannot_delete_files(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perm = db_session.query(Permission).filter(
        Permission.role == UserRole.operator,
        Permission.resource == "files",
        Permission.action == "delete",
    ).first()
    assert perm is None


def test_pipelines_execute_seeded_for_operator(db_session):
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    perm = db_session.query(Permission).filter(
        Permission.role == UserRole.operator,
        Permission.resource == "pipelines",
        Permission.action == "execute",
    ).first()
    assert perm is not None


def test_check_permission_admin_always_true(db_session):
    """Admin bypasses the table — must return True even with no permissions seeded."""
    from backend.dependencies import check_permission
    user = User(username="testadmin", hashed_password="x", role=UserRole.admin)
    db_session.add(user)
    db_session.commit()
    # No seed_permissions call — table is empty
    assert check_permission(db_session, user, "scripts", "execute") is True
    assert check_permission(db_session, user, "users", "delete") is True


def test_check_permission_readonly_cannot_execute(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "execute") is False


def test_check_permission_readonly_can_read(db_session):
    from backend.dependencies import check_permission
    from backend.scripts.init_db import seed_permissions
    seed_permissions(db_session)
    user = User(username="viewer", hashed_password="x", role=UserRole.readonly)
    db_session.add(user)
    db_session.commit()
    assert check_permission(db_session, user, "scripts", "read") is True
