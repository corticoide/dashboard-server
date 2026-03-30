def test_gzip_compression_on_json_response(test_app):
    token = test_app.post(
        "/api/auth/login", json={"username": "admin", "password": "adminpass"}
    ).json()["access_token"]
    r = test_app.get(
        "/api/logs/executions/stats",
        headers={"Authorization": f"Bearer {token}", "Accept-Encoding": "gzip"},
    )
    assert r.status_code == 200
    assert r.headers.get("content-encoding") == "gzip"
