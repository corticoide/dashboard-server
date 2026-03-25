import pytest
from backend.services.auth_service import (
    hash_password, verify_password, create_access_token, decode_token
)

def test_hash_and_verify_password():
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong", hashed)

def test_create_and_decode_access_token():
    token = create_access_token(user_id=1, username="alice", role="admin")
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "alice"
    assert payload["role"] == "admin"

def test_decode_invalid_token_raises():
    with pytest.raises(Exception):
        decode_token("not.a.real.token")
