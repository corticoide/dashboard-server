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


def test_list_permissions(test_app):
    token = get_token(test_app)
    r = test_app.get("/api/admin/permissions", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert "operator" in data
    assert "readonly" in data
    ro = data["readonly"]
    assert all(p["action"] == "read" for p in ro)
    op = data["operator"]
    assert any(p["resource"] == "scripts" and p["action"] == "execute" for p in op)


def test_update_permissions_operator(test_app):
    token = get_token(test_app)
    new_perms = [
        {"resource": "system", "action": "read"},
        {"resource": "logs",   "action": "read"},
    ]
    r = test_app.put(
        "/api/admin/permissions/operator",
        json=new_perms,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200
    r2 = test_app.get("/api/admin/permissions", headers={"Authorization": f"Bearer {token}"})
    op = r2.json()["operator"]
    assert len(op) == 2
    assert any(p["resource"] == "system" and p["action"] == "read" for p in op)


def test_update_permissions_admin_forbidden(test_app):
    token = get_token(test_app)
    r = test_app.put(
        "/api/admin/permissions/admin",
        json=[{"resource": "system", "action": "read"}],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_update_permissions_invalid_role(test_app):
    token = get_token(test_app)
    r = test_app.put(
        "/api/admin/permissions/superuser",
        json=[{"resource": "system", "action": "read"}],
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400


def test_non_admin_cannot_list_permissions(test_app):
    admin_token = get_token(test_app)
    test_app.post("/api/admin/users", json={"username": "op1", "password": "pass", "role": "operator"},
                  headers={"Authorization": f"Bearer {admin_token}"})
    op_token = get_token(test_app, "op1", "pass")
    r = test_app.get("/api/admin/permissions", headers={"Authorization": f"Bearer {op_token}"})
    assert r.status_code == 403
