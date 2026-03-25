import pytest
from unittest.mock import MagicMock
from fastapi import HTTPException
from backend.dependencies import require_role
from backend.models.user import User, UserRole

def make_mock_user(role: UserRole) -> User:
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "alice"
    user.role = role
    return user

def test_require_role_passes_when_role_matches():
    user = make_mock_user(UserRole.admin)
    checker = require_role("admin")
    result = checker(current_user=user)
    assert result == user

def test_require_role_passes_when_higher_role():
    user = make_mock_user(UserRole.admin)
    checker = require_role("operator")
    result = checker(current_user=user)
    assert result == user

def test_require_role_raises_when_role_insufficient():
    user = make_mock_user(UserRole.readonly)
    checker = require_role("admin")
    with pytest.raises(HTTPException) as exc:
        checker(current_user=user)
    assert exc.value.status_code == 403
