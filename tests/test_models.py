from backend.models.user import User, UserRole

def test_create_user(db_session):
    user = User(username="alice", hashed_password="hash", role=UserRole.admin)
    db_session.add(user)
    db_session.commit()
    found = db_session.query(User).filter_by(username="alice").first()
    assert found is not None
    assert found.role == UserRole.admin

def test_user_roles_are_valid():
    assert set(r.value for r in UserRole) == {"admin", "operator", "readonly"}
