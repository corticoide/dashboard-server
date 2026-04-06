import pytest
import os
import time
from pathlib import Path


@pytest.fixture
def tmp(tmp_path):
    (tmp_path / "src.txt").write_text("hello world")
    (tmp_path / "subdir").mkdir()
    return tmp_path


def test_move_file(tmp):
    from backend.services.pipeline_modules import move_file
    src, dst = str(tmp / "src.txt"), str(tmp / "moved.txt")
    code, out = move_file({"src": src, "dst": dst}, {})
    assert code == 0
    assert Path(dst).exists() and not Path(src).exists()


def test_copy_file(tmp):
    from backend.services.pipeline_modules import copy_file
    src, dst = str(tmp / "src.txt"), str(tmp / "copy.txt")
    code, out = copy_file({"src": src, "dst": dst}, {})
    assert code == 0 and Path(dst).exists() and Path(src).exists()


def test_delete_file(tmp):
    from backend.services.pipeline_modules import delete_file
    path = str(tmp / "src.txt")
    code, out = delete_file({"path": path}, {})
    assert code == 0 and not Path(path).exists()


def test_mkdir(tmp):
    from backend.services.pipeline_modules import mkdir
    path = str(tmp / "newdir" / "nested")
    code, out = mkdir({"path": path}, {})
    assert code == 0 and Path(path).is_dir()


def test_write_file_overwrite(tmp):
    from backend.services.pipeline_modules import write_file
    path = str(tmp / "out.txt")
    code, _ = write_file({"path": path, "content": "hello", "mode": "overwrite"}, {})
    assert code == 0 and Path(path).read_text() == "hello"


def test_write_file_append(tmp):
    from backend.services.pipeline_modules import write_file
    path = str(tmp / "out.txt")
    write_file({"path": path, "content": "line1\n", "mode": "overwrite"}, {})
    write_file({"path": path, "content": "line2\n", "mode": "append"}, {})
    assert Path(path).read_text() == "line1\nline2\n"


def test_rename_file(tmp):
    from backend.services.pipeline_modules import rename_file
    src = str(tmp / "src.txt")
    code, _ = rename_file({"path": src, "new_name": "renamed.txt", "use_timestamp": False}, {})
    assert code == 0 and (tmp / "renamed.txt").exists()


def test_rename_file_with_timestamp(tmp):
    from backend.services.pipeline_modules import rename_file
    src = str(tmp / "src.txt")
    code, _ = rename_file({"path": src, "new_name": "bkp.txt", "use_timestamp": True}, {})
    assert code == 0 and len(list(tmp.glob("*_bkp.txt"))) == 1


def test_check_exists_success(tmp):
    from backend.services.pipeline_modules import check_exists
    code, _ = check_exists({"path": str(tmp / "src.txt"), "type": "file"}, {})
    assert code == 0


def test_check_exists_failure(tmp):
    from backend.services.pipeline_modules import check_exists
    code, _ = check_exists({"path": str(tmp / "nope.txt"), "type": "file"}, {})
    assert code == 1


def test_delay():
    from backend.services.pipeline_modules import delay
    start = time.time()
    code, _ = delay({"seconds": 0.1}, {})
    assert code == 0 and time.time() - start >= 0.09


def test_log_module():
    from backend.services.pipeline_modules import log_message
    code, out = log_message({"message": "hello pipeline", "level": "info"}, {})
    assert code == 0 and "hello pipeline" in out


def test_compress_decompress(tmp):
    from backend.services.pipeline_modules import compress, decompress
    src, archive = str(tmp / "src.txt"), str(tmp / "archive.tar.gz")
    out_dir = str(tmp / "extracted")
    code, _ = compress({"src": src, "dst": archive, "format": "tar.gz"}, {})
    assert code == 0 and Path(archive).exists()
    os.makedirs(out_dir)
    code, _ = decompress({"src": archive, "dst": out_dir}, {})
    assert code == 0


def test_load_env(tmp):
    from backend.services.pipeline_modules import load_env
    env_file = tmp / ".env"
    env_file.write_text("MY_VAR=hello\nOTHER=world\n")
    context = {}
    code, _ = load_env({"path": str(env_file)}, context)
    assert code == 0 and context["MY_VAR"] == "hello" and context["OTHER"] == "world"
