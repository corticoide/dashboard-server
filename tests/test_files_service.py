import pytest
from pathlib import Path
from backend.services.files_service import list_dir, read_file, make_dir, rename_path, delete_path

@pytest.fixture
def tmp(tmp_path):
    (tmp_path / "subdir").mkdir()
    (tmp_path / "hello.txt").write_text("hello world")
    (tmp_path / "subdir" / "inner.txt").write_text("inner")
    return tmp_path

def test_list_dir_returns_entries(tmp):
    result = list_dir(str(tmp))
    names = [e.name for e in result.entries]
    assert "subdir" in names
    assert "hello.txt" in names

def test_list_dir_dirs_first(tmp):
    result = list_dir(str(tmp))
    assert result.entries[0].is_dir

def test_list_dir_not_found():
    with pytest.raises(FileNotFoundError):
        list_dir("/nonexistent_path_xyz_abc")

def test_read_file(tmp):
    result = read_file(str(tmp / "hello.txt"))
    assert result.content == "hello world"
    assert result.size == 11

def test_read_file_too_large(tmp):
    big = tmp / "big.bin"
    big.write_bytes(b"x" * (6 * 1024 * 1024))
    with pytest.raises(ValueError, match="too large"):
        read_file(str(big))

def test_mkdir(tmp):
    make_dir(str(tmp / "newdir"))
    assert (tmp / "newdir").is_dir()

def test_rename(tmp):
    rename_path(str(tmp / "hello.txt"), str(tmp / "renamed.txt"))
    assert (tmp / "renamed.txt").exists()
    assert not (tmp / "hello.txt").exists()

def test_delete_file(tmp):
    delete_path(str(tmp / "hello.txt"))
    assert not (tmp / "hello.txt").exists()

def test_delete_dir(tmp):
    delete_path(str(tmp / "subdir"))
    assert not (tmp / "subdir").exists()

def test_path_traversal_blocked():
    from backend.services.files_service import _safe_path
    p = _safe_path("/etc/hosts")
    assert p == Path("/etc/hosts")
