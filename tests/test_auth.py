def test_login_success(test_app):
    response = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"

def test_login_wrong_password(test_app):
    response = test_app.post("/api/auth/login", json={"username": "admin", "password": "wrong"})
    assert response.status_code == 401

def test_login_unknown_user(test_app):
    response = test_app.post("/api/auth/login", json={"username": "ghost", "password": "x"})
    assert response.status_code == 401

def test_protected_route_without_token(test_app):
    response = test_app.get("/api/system/metrics")
    assert response.status_code == 403

def test_protected_route_with_valid_token(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    response = test_app.get("/api/system/metrics", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
