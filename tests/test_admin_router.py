def get_token(client, username="admin", password="adminpass"):
    r = client.post("/api/auth/login", json={"username": username, "password": password})
    return r.json()["access_token"]


def test_list_users(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/admin/users", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_create_user(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={"username": "newuser", "password": "securepass123", "role": "operator"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 201
    assert r.json()["username"] == "newuser"
    assert r.json()["role"] == "operator"


def test_create_duplicate_user(test_app):
    token = get_token(test_app)
    test_app.post("/api/admin/users", json={"username": "dupe", "password": "pass123", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    r = test_app.post("/api/admin/users", json={"username": "dupe", "password": "pass456", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 409


def test_update_user_role(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={"username": "roletest", "password": "pass", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    r = test_app.patch(f"/api/admin/users/{user_id}", json={"role": "operator"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "operator"


def test_deactivate_user(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={"username": "deact", "password": "pass", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    r = test_app.patch(f"/api/admin/users/{user_id}", json={"is_active": False}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["is_active"] is False


def test_delete_user(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={"username": "todelete", "password": "pass", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    r = test_app.delete(f"/api/admin/users/{user_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_cannot_delete_self(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    admin_id = r.json()["id"]
    r = test_app.delete(f"/api/admin/users/{admin_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400


def test_non_admin_cannot_access(test_app):
    token = get_token(test_app)
    test_app.post("/api/admin/users", json={"username": "viewer", "password": "viewerpass", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    viewer_token = get_token(test_app, "viewer", "viewerpass")
    r = test_app.get("/api/admin/users", headers={"Authorization": f"Bearer {viewer_token}"})
    assert r.status_code == 403


def test_inactive_user_cannot_login(test_app):
    token = get_token(test_app)
    r = test_app.post("/api/admin/users", json={"username": "inactive", "password": "pass", "role": "readonly"}, headers={"Authorization": f"Bearer {token}"})
    user_id = r.json()["id"]
    test_app.patch(f"/api/admin/users/{user_id}", json={"is_active": False}, headers={"Authorization": f"Bearer {token}"})
    r = test_app.post("/api/auth/login", json={"username": "inactive", "password": "pass"})
    assert r.status_code == 403
