import os
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from backend.dependencies import require_permission

router = APIRouter(prefix="/api/system-logs", tags=["system-logs"])

LOG_ROOT = Path("/var/log")


def _validate_path(path_str: str) -> Path:
    """Resolve path and ensure it is under LOG_ROOT. Raises HTTPException otherwise."""
    try:
        p = Path(path_str).resolve()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid path")
    if not p.is_relative_to(LOG_ROOT):
        raise HTTPException(status_code=403, detail="Path outside /var/log")
    return p


def _build_tree(root: Path) -> List[dict]:
    """Recursively list files and directories under root."""
    result = []
    try:
        entries = sorted(root.iterdir(), key=lambda e: (e.is_file(), e.name))
    except PermissionError:
        return result
    for entry in entries:
        if entry.is_dir() and not entry.is_symlink():
            result.append({
                "name": entry.name,
                "path": str(entry),
                "is_dir": True,
                "children": _build_tree(entry),
            })
        elif entry.is_file() and not entry.is_symlink():
            readable = os.access(entry, os.R_OK)
            try:
                size_bytes = entry.stat().st_size
            except OSError:
                size_bytes = 0
            result.append({
                "name": entry.name,
                "path": str(entry),
                "is_dir": False,
                "size_bytes": size_bytes,
                "readable": readable,
            })
    return result


@router.get("/tree")
def get_tree(user=Depends(require_permission("system_logs", "read"))):
    return _build_tree(LOG_ROOT)


@router.get("/read")
def read_log(
    path: str = Query(...),
    lines: int = Query(100, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    user=Depends(require_permission("system_logs", "read")),
):
    p = _validate_path(path)
    if not p.is_file():
        raise HTTPException(status_code=404, detail="Not a file")
    try:
        with open(p, "rb") as f:
            content = f.read().decode("utf-8", errors="replace")
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied")
    all_lines = content.splitlines()
    total = len(all_lines)
    end = max(0, total - offset)
    start = max(0, end - lines)
    return {
        "path": str(p),
        "total_lines": total,
        "lines": all_lines[start:end],
    }
