from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Header
from fastapi.responses import StreamingResponse
from pathlib import Path
from typing import List, Optional
from backend.core.logging import get_audit_logger
from backend.dependencies import get_current_user, require_role
from backend.models.user import UserRole
from backend.schemas.files import DirListing, FileContent, MkdirRequest, RenameRequest, FileWriteRequest
from backend.services.files_service import (
    list_dir, read_file, stream_file, make_dir, rename_path, delete_path, write_file, _safe_path
)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/list", response_model=DirListing)
def api_list(path: str = Query("/"), user=Depends(get_current_user)):
    try:
        return list_dir(path)
    except (FileNotFoundError, NotADirectoryError) as e:
        raise HTTPException(404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/content", response_model=FileContent)
def api_content(
    path: str = Query(...),
    user=Depends(get_current_user),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        return read_file(path, sudo_password=x_sudo_password)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, IsADirectoryError) as e:
        raise HTTPException(400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=f"{str(e)} — sudo password required")
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))


@router.get("/download")
def api_download(
    path: str = Query(...),
    user=Depends(get_current_user),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        iterator, filename, size = stream_file(path, sudo_password=x_sudo_password)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=f"{str(e)} — sudo password required")
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(size),
    }
    return StreamingResponse(iterator, media_type="application/octet-stream", headers=headers)


@router.post("/mkdir")
def api_mkdir(body: MkdirRequest, user=Depends(require_role(UserRole.admin))):
    try:
        make_dir(body.path)
        return {"ok": True, "path": body.path}
    except FileExistsError:
        raise HTTPException(409, detail="Already exists")
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.post("/rename")
def api_rename(body: RenameRequest, user=Depends(require_role(UserRole.admin))):
    try:
        rename_path(body.source, body.destination)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.delete("/delete")
def api_delete(path: str = Query(...), user=Depends(require_role(UserRole.admin))):
    try:
        delete_path(path)
        get_audit_logger().info("file_delete user=%s path=%s", user.username, path)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.post("/upload")
def api_upload(
    path: str = Query(...),
    file: UploadFile = File(...),
    user=Depends(require_role(UserRole.operator)),
):
    try:
        safe_name = Path(file.filename).name if file.filename else ""
        if not safe_name or safe_name in (".", ".."):
            raise HTTPException(400, detail="Invalid filename")
        target = _safe_path(path) / safe_name
        with open(target, "wb") as f:
            while chunk := file.file.read(65536):
                f.write(chunk)
        return {"ok": True, "path": str(target)}
    except HTTPException:
        raise
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.put("/content")
def api_write(
    body: FileWriteRequest,
    path: str = Query(...),
    user=Depends(require_role(UserRole.admin)),
    x_sudo_password: Optional[str] = Header(None),
):
    try:
        write_file(path, body.content, sudo_password=x_sudo_password)
        get_audit_logger().info("file_write user=%s path=%s", user.username, path)
        return {"ok": True}
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(500, detail=str(e))
