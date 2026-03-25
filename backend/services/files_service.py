import os
import stat
import shutil
import grp
import pwd
from pathlib import Path
from datetime import datetime
from typing import Iterator
from backend.schemas.files import FileEntry, DirListing, FileContent

ALLOWED_ROOT = Path("/")
MAX_READ_BYTES = 5 * 1024 * 1024  # 5 MB

LANGUAGE_MAP = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".vue": "html", ".html": "html", ".css": "css", ".scss": "scss",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".sh": "shell", ".bash": "shell", ".md": "markdown",
    ".txt": "plaintext", ".log": "plaintext", ".conf": "ini",
    ".xml": "xml", ".toml": "toml", ".env": "ini",
    ".c": "c", ".cpp": "cpp", ".h": "cpp", ".cs": "csharp",
    ".go": "go", ".rs": "rust", ".java": "java",
}


def _safe_path(path: str) -> Path:
    try:
        resolved = Path(path).resolve()
    except Exception:
        raise ValueError(f"Invalid path: {path!r}")
    try:
        resolved.relative_to(ALLOWED_ROOT)
    except ValueError:
        raise PermissionError(f"Path outside allowed root: {path!r}")
    return resolved


def _stat_entry(item: Path) -> FileEntry:
    st = item.lstat()
    try:
        owner = pwd.getpwuid(st.st_uid).pw_name
    except (KeyError, ImportError):
        owner = str(st.st_uid)
    try:
        group = grp.getgrgid(st.st_gid).gr_name
    except (KeyError, ImportError):
        group = str(st.st_gid)

    mode = st.st_mode
    perms = ""
    for r, w, x in [
        (stat.S_IRUSR, stat.S_IWUSR, stat.S_IXUSR),
        (stat.S_IRGRP, stat.S_IWGRP, stat.S_IXGRP),
        (stat.S_IROTH, stat.S_IWOTH, stat.S_IXOTH),
    ]:
        perms += ("r" if mode & r else "-")
        perms += ("w" if mode & w else "-")
        perms += ("x" if mode & x else "-")

    return FileEntry(
        name=item.name,
        path=str(item),
        is_dir=item.is_dir(),
        size=st.st_size if not item.is_dir() else None,
        permissions=perms,
        owner=owner,
        group=group,
        modified=datetime.fromtimestamp(st.st_mtime).isoformat(),
    )


def list_dir(path: str) -> DirListing:
    p = _safe_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {path}")
    if not p.is_dir():
        raise NotADirectoryError(f"Not a directory: {path}")

    entries = []
    try:
        items = sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
        for item in items:
            try:
                entries.append(_stat_entry(item))
            except (PermissionError, OSError):
                pass
    except PermissionError as e:
        raise PermissionError(f"Cannot read directory: {e}")

    parent = str(p.parent) if str(p) != str(p.root) else None
    return DirListing(path=str(p), parent=parent, entries=entries)


def read_file(path: str) -> FileContent:
    p = _safe_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {path}")
    if p.is_dir():
        raise IsADirectoryError(f"Is a directory: {path}")
    size = p.stat().st_size
    if size > MAX_READ_BYTES:
        raise ValueError(f"File too large to read ({size} bytes, max {MAX_READ_BYTES})")
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        raise ValueError(f"Cannot read file as text: {e}")
    language = LANGUAGE_MAP.get(p.suffix.lower(), "plaintext")
    return FileContent(path=str(p), content=content, size=size, language=language)


def stream_file(path: str):
    p = _safe_path(path)
    if not p.exists() or p.is_dir():
        raise FileNotFoundError(f"Not found or is a directory: {path}")
    size = p.stat().st_size

    def _iter():
        with open(p, "rb") as f:
            while chunk := f.read(65536):
                yield chunk

    return _iter(), p.name, size


def make_dir(path: str) -> None:
    p = _safe_path(path)
    p.mkdir(parents=False, exist_ok=False)


def rename_path(source: str, destination: str) -> None:
    src = _safe_path(source)
    dst = _safe_path(destination)
    if not src.exists():
        raise FileNotFoundError(f"Source not found: {source}")
    src.rename(dst)


def delete_path(path: str) -> None:
    p = _safe_path(path)
    if not p.exists():
        raise FileNotFoundError(f"Not found: {path}")
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink()


def write_file(path: str, content: str) -> None:
    p = _safe_path(path)
    p.write_text(content, encoding="utf-8")
