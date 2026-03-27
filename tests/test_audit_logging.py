import os
import tempfile
from unittest.mock import patch, MagicMock


def test_file_write_emits_audit_log(test_app):
    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        f.write(b"original")
        fpath = f.name
    try:
        with patch("backend.routers.files.get_audit_logger") as mock_logger:
            mock_log = MagicMock()
            mock_logger.return_value = mock_log
            r = test_app.put(
                f"/api/files/content?path={fpath}",
                headers=headers,
                json={"content": "new content"},
            )
            assert r.status_code == 200
            mock_log.info.assert_called_once()
            assert "file_write" in mock_log.info.call_args[0][0]
    finally:
        os.unlink(fpath)


def test_file_delete_emits_audit_log(test_app):
    token = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
        fpath = f.name
    with patch("backend.routers.files.get_audit_logger") as mock_logger:
        mock_log = MagicMock()
        mock_logger.return_value = mock_log
        r = test_app.delete(f"/api/files/delete?path={fpath}", headers=headers)
        assert r.status_code == 200
        mock_log.info.assert_called_once()
        assert "file_delete" in mock_log.info.call_args[0][0]
