import os
import tempfile


def _login(test_app):
    r = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    return r.json()["access_token"]


def test_tree_requires_auth(test_app):
    r = test_app.get("/api/system-logs/tree")
    assert r.status_code == 403


def test_read_rejects_path_outside_var_log(test_app):
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}
    r = test_app.get("/api/system-logs/read?path=/etc/passwd", headers=headers)
    assert r.status_code == 403


def test_read_returns_lines(test_app, tmp_path):
    from unittest.mock import patch
    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    log_file = tmp_path / "test.log"
    log_file.write_text("line1\nline2\nline3\n")

    with patch("backend.routers.system_logs.LOG_ROOT", tmp_path):
        r = test_app.get(
            f"/api/system-logs/read?path={log_file}&lines=10",
            headers=headers,
        )

    assert r.status_code == 200
    data = r.json()
    assert data["total_lines"] == 3
    assert data["lines"] == ["line1", "line2", "line3"]


def test_tree_returns_structure(test_app, tmp_path):
    from unittest.mock import patch

    (tmp_path / "syslog").write_text("x")
    sub = tmp_path / "nginx"
    sub.mkdir()
    (sub / "access.log").write_text("y")

    token = _login(test_app)
    headers = {"Authorization": f"Bearer {token}"}

    with patch("backend.routers.system_logs.LOG_ROOT", tmp_path):
        r = test_app.get("/api/system-logs/tree", headers=headers)

    assert r.status_code == 200
    names = {entry["name"] for entry in r.json()}
    assert "syslog" in names
    assert "nginx" in names


def test_ws_log_tail_rejects_bad_token(test_app):
    from starlette.websockets import WebSocketDisconnect
    try:
        with test_app.websocket_connect("/api/ws/log-tail?path=/var/log/syslog&token=bad") as ws:
            ws.receive_text()
            assert False, "Expected disconnect"
    except WebSocketDisconnect:
        pass  # Expected — server closes connection on bad token
