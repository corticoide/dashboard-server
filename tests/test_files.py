from unittest.mock import patch
from backend.schemas.files import DirListing, FileEntry, FileContent

MOCK_ENTRY = FileEntry(
    name="test.txt", path="/tmp/test.txt", is_dir=False,
    size=100, permissions="rw-r--r--", owner="root", group="root",
    modified="2026-03-25T10:00:00"
)
MOCK_LISTING = DirListing(path="/tmp", parent="/", entries=[MOCK_ENTRY])

def test_list_requires_auth(test_app):
    r = test_app.get("/api/files/list?path=/tmp")
    assert r.status_code == 403

def test_list_returns_entries(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.files.list_dir", return_value=MOCK_LISTING):
        r = test_app.get("/api/files/list?path=/tmp", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    data = r.json()
    assert data["path"] == "/tmp"
    assert len(data["entries"]) == 1

def test_read_file_returns_content(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    mock_content = FileContent(path="/tmp/test.txt", content="hello", size=5, language="plaintext")
    with patch("backend.routers.files.read_file", return_value=mock_content):
        r = test_app.get("/api/files/content?path=/tmp/test.txt",
                         headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["content"] == "hello"

def test_delete_as_admin(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.files.delete_path") as mock_del:
        r = test_app.delete("/api/files/delete?path=/tmp/test.txt",
                            headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    mock_del.assert_called_once_with("/tmp/test.txt")

def test_mkdir_as_admin(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.files.make_dir") as mock_mkdir:
        r = test_app.post("/api/files/mkdir", json={"path": "/tmp/newdir"},
                          headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    mock_mkdir.assert_called_once_with("/tmp/newdir")

def test_upload_sanitizes_filename(test_app, tmp_path):
    """Filename with path components must be stripped to basename only."""
    import io
    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    data = {"file": ("../../evil.txt", io.BytesIO(b"pwned"), "text/plain")}
    r = test_app.post(
        f"/api/files/upload?path={tmp_path}",
        headers=headers,
        files=data,
    )
    assert r.status_code == 200
    written = r.json()["path"]
    assert written.startswith(str(tmp_path)), f"Path traversal! Got: {written}"
    assert "evil.txt" in written
    assert ".." not in written
