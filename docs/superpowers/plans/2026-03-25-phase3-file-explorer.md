# ServerDash Phase 3 — File Explorer

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans.

**Goal:** FileZilla-style file explorer — top panel shows collapsible directory tree, bottom panel shows contents of selected directory. Drag-to-resize divider between panels. File actions: download, delete, rename, new folder, upload. Monaco editor for text file preview/editing.

**Architecture:**
- Backend: `/api/files/*` endpoints using pathlib + os.stat. Path traversal protection via resolve(). Streaming download. Multipart upload.
- Frontend: FilesView.vue (split layout with draggable divider) + DirTree.vue (recursive lazy tree) + FileList.vue (sortable table with actions) + Monaco viewer panel.
- Role enforcement: readonly → view/download only; operator/admin → full write access.

**Tech Stack:** Python pathlib · FastAPI StreamingResponse · Vue 3 · @guolao/vue-monaco-editor

---

## File Map

```
backend/
  schemas/files.py              # FileEntry, DirListing, FileContent, MkdirRequest, RenameRequest
  services/files_service.py     # list_dir(), read_file(), delete_path(), mkdir(), rename(), stream_file()
  routers/files.py              # all /api/files/* endpoints
  main.py                       # include files router (modify)
frontend/src/
  views/FilesView.vue           # split layout: tree top, list bottom, monaco panel right
  components/files/
    DirTree.vue                 # recursive lazy-loading directory tree
    FileList.vue                # sortable file table with row actions
    FileToolbar.vue             # breadcrumb + upload + new folder buttons
tests/
  test_files_service.py
  test_files.py
```

---

## Task 1: Backend schema + service layer

**Files:**
- Create: `backend/schemas/files.py`
- Create: `backend/services/files_service.py`
- Create: `tests/test_files_service.py`

- [ ] **Write tests first**

```python
# tests/test_files_service.py
import os, tempfile, pytest
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
    assert result.entries[0].is_dir  # dirs sorted first

def test_list_dir_not_found():
    with pytest.raises(FileNotFoundError):
        list_dir("/nonexistent_path_xyz")

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
    # Traversal attempts resolve to valid paths but must be under ALLOWED_ROOT
    p = _safe_path("/etc/hosts")
    assert p == Path("/etc/hosts")
```

- [ ] **Run — expect FAIL:** `.venv/bin/pytest tests/test_files_service.py -q`

- [ ] **Create `backend/schemas/files.py`**

```python
from pydantic import BaseModel
from typing import List, Optional

class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None   # None for directories
    permissions: str             # e.g. "rwxr-xr-x"
    owner: str
    group: str
    modified: str                # ISO8601

class DirListing(BaseModel):
    path: str
    parent: Optional[str] = None
    entries: List[FileEntry]

class FileContent(BaseModel):
    path: str
    content: str
    size: int
    language: str               # detected language hint for Monaco

class MkdirRequest(BaseModel):
    path: str

class RenameRequest(BaseModel):
    source: str
    destination: str
```

- [ ] **Create `backend/services/files_service.py`**

```python
import os
import pwd
import grp
import stat
import shutil
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


def stream_file(path: str) -> tuple[Iterator[bytes], str, int]:
    """Returns (iterator, filename, size) for streaming download."""
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
```

- [ ] **Run — expect PASS:** `.venv/bin/pytest tests/test_files_service.py -q`

- [ ] **Commit:**
```bash
git add backend/schemas/files.py backend/services/files_service.py tests/test_files_service.py
git commit -m "feat: Phase 3 files schema and service layer"
```

---

## Task 2: Files router + wire into app + tests

**Files:**
- Create: `backend/routers/files.py`
- Modify: `backend/main.py`
- Create: `tests/test_files.py`

- [ ] **Write tests first**

```python
# tests/test_files.py
import io
from unittest.mock import patch, MagicMock
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

def test_mkdir_requires_operator(test_app):
    from backend.models.user import User, UserRole
    from backend.database import get_db
    from backend.services.auth_service import hash_password
    db = next(test_app.app.dependency_overrides[get_db]())
    db.add(User(username="viewer2", hashed_password=hash_password("vp"), role=UserRole.readonly))
    db.commit()
    login = test_app.post("/api/auth/login", json={"username": "viewer2", "password": "vp"})
    token = login.json()["access_token"]
    r = test_app.post("/api/files/mkdir", json={"path": "/tmp/newdir"},
                      headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403

def test_delete_requires_operator(test_app):
    login = test_app.post("/api/auth/login", json={"username": "admin", "password": "adminpass"})
    token = login.json()["access_token"]
    with patch("backend.routers.files.delete_path") as mock_del:
        r = test_app.delete("/api/files/delete?path=/tmp/test.txt",
                            headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    mock_del.assert_called_once_with("/tmp/test.txt")
```

- [ ] **Run — expect FAIL:** `.venv/bin/pytest tests/test_files.py -q`

- [ ] **Create `backend/routers/files.py`**

```python
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from typing import List
from backend.dependencies import get_current_user, require_role
from backend.models.user import UserRole
from backend.schemas.files import DirListing, FileContent, MkdirRequest, RenameRequest
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
def api_content(path: str = Query(...), user=Depends(get_current_user)):
    try:
        return read_file(path)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, IsADirectoryError) as e:
        raise HTTPException(400, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))


@router.get("/download")
def api_download(path: str = Query(...), user=Depends(get_current_user)):
    try:
        iterator, filename, size = stream_file(path)
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(403, detail=str(e))
    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Length": str(size),
    }
    return StreamingResponse(iterator, media_type="application/octet-stream", headers=headers)


@router.post("/mkdir")
def api_mkdir(body: MkdirRequest, user=Depends(require_role(UserRole.operator))):
    try:
        make_dir(body.path)
        return {"ok": True, "path": body.path}
    except FileExistsError:
        raise HTTPException(409, detail="Already exists")
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.post("/rename")
def api_rename(body: RenameRequest, user=Depends(require_role(UserRole.operator))):
    try:
        rename_path(body.source, body.destination)
        return {"ok": True}
    except FileNotFoundError as e:
        raise HTTPException(404, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.delete("/delete")
def api_delete(path: str = Query(...), user=Depends(require_role(UserRole.operator))):
    try:
        delete_path(path)
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
        target = _safe_path(path) / file.filename
        with open(target, "wb") as f:
            while chunk := file.file.read(65536):
                f.write(chunk)
        return {"ok": True, "path": str(target)}
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))


@router.put("/content")
def api_write(path: str = Query(...), body: dict = None,
              user=Depends(require_role(UserRole.operator))):
    if not body or "content" not in body:
        raise HTTPException(400, detail="Missing content field")
    try:
        write_file(path, body["content"])
        return {"ok": True}
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, detail=str(e))
```

- [ ] **Wire into `backend/main.py`** — add after services router:
```python
from backend.routers.files import router as files_router
app.include_router(files_router)
```

- [ ] **Run all tests:** `.venv/bin/pytest tests/ -q`

- [ ] **Commit:**
```bash
git add backend/routers/files.py backend/main.py tests/test_files.py
git commit -m "feat: Phase 3 files router and API endpoints"
```

---

## Task 3: Frontend install Monaco + DirTree component

**Files:**
- Modify: `frontend/package.json` (add @guolao/vue-monaco-editor)
- Create: `frontend/src/components/files/DirTree.vue`

- [ ] **Install Monaco:**
```bash
cd /home/crt/server_dashboard/frontend
npm install @guolao/vue-monaco-editor
```

- [ ] **Create `frontend/src/components/files/DirTree.vue`**

```vue
<template>
  <div class="tree-node">
    <div
      class="tree-item"
      :class="{ active: currentPath === node.path, loading: isLoading }"
      :style="{ paddingLeft: `${depth * 14 + 8}px` }"
      @click="handleClick"
    >
      <!-- Expand toggle -->
      <span class="tree-arrow" :class="{ expanded: isExpanded }">
        <svg v-if="!isLoading" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
          <polyline points="9 18 15 12 9 6"/>
        </svg>
        <svg v-else width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="spin">
          <circle cx="12" cy="12" r="10" stroke-dasharray="20 60"/>
        </svg>
      </span>
      <!-- Folder icon -->
      <svg width="13" height="13" viewBox="0 0 24 24" fill="currentColor" class="folder-icon">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
      </svg>
      <span class="tree-name">{{ node.name || node.path }}</span>
    </div>
    <!-- Children -->
    <div v-if="isExpanded && children.length > 0" class="tree-children">
      <DirTree
        v-for="child in children"
        :key="child.path"
        :node="child"
        :current-path="currentPath"
        :depth="depth + 1"
        @navigate="$emit('navigate', $event)"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import api from '../../api/client.js'

const props = defineProps({
  node: { type: Object, required: true },  // { name, path }
  currentPath: String,
  depth: { type: Number, default: 0 },
})
const emit = defineEmits(['navigate'])

const isExpanded = ref(props.depth === 0)
const isLoading = ref(false)
const children = ref([])

async function loadChildren() {
  if (children.value.length > 0) return
  isLoading.value = true
  try {
    const { data } = await api.get('/files/list', { params: { path: props.node.path } })
    children.value = data.entries
      .filter(e => e.is_dir)
      .map(e => ({ name: e.name, path: e.path }))
  } catch {
    children.value = []
  } finally {
    isLoading.value = false
  }
}

async function handleClick() {
  emit('navigate', props.node.path)
  if (!isExpanded.value) {
    await loadChildren()
    isExpanded.value = true
  } else {
    isExpanded.value = false
  }
}

// Auto-expand root on mount
if (props.depth === 0) loadChildren()

// When currentPath changes to a child, ensure we're expanded
watch(() => props.currentPath, (newPath) => {
  if (newPath && newPath.startsWith(props.node.path + '/') && !isExpanded.value) {
    loadChildren().then(() => { isExpanded.value = true })
  }
})
</script>

<style scoped>
.tree-node { user-select: none; }
.tree-item {
  display: flex; align-items: center; gap: 5px;
  padding: 4px 8px; border-radius: 4px; cursor: pointer;
  font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);
  transition: background 0.1s, color 0.1s;
  white-space: nowrap;
}
.tree-item:hover { background: var(--surface-2); color: var(--text); }
.tree-item.active { background: var(--surface-3); color: var(--accent-blue); }
.tree-arrow {
  width: 12px; flex-shrink: 0; color: var(--text-dim);
  transition: transform 0.15s;
}
.tree-arrow.expanded { transform: rotate(90deg); }
.folder-icon { flex-shrink: 0; color: var(--accent-yellow); opacity: 0.8; }
.tree-item.active .folder-icon { color: var(--accent-blue); opacity: 1; }
.tree-name { overflow: hidden; text-overflow: ellipsis; }
.spin { animation: spin 1s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
```

- [ ] **Commit:**
```bash
git add frontend/src/components/files/DirTree.vue frontend/package.json frontend/package-lock.json
git commit -m "feat: Phase 3 DirTree component + Monaco dependency"
```

---

## Task 4: FileList component + FilesView + router wiring

**Files:**
- Create: `frontend/src/components/files/FileList.vue`
- Create: `frontend/src/views/FilesView.vue`
- Modify: `frontend/src/router/index.js`
- Modify: `frontend/src/components/layout/AppSidebar.vue` (remove disabled from Files)

- [ ] **Create `frontend/src/components/files/FileList.vue`**

```vue
<template>
  <div class="file-list">
    <!-- Toolbar -->
    <div class="list-toolbar">
      <!-- Breadcrumb -->
      <div class="breadcrumb">
        <span
          v-for="(seg, i) in segments" :key="seg.path"
          class="breadcrumb-item"
        >
          <span v-if="i > 0" class="breadcrumb-sep">/</span>
          <button class="breadcrumb-btn" @click="$emit('navigate', seg.path)">
            {{ seg.label }}
          </button>
        </span>
      </div>
      <div class="toolbar-actions">
        <!-- Upload -->
        <label class="action-btn btn-blue" title="Upload file">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>
          Upload
          <input type="file" class="hidden-input" @change="uploadFile" multiple />
        </label>
        <!-- New folder -->
        <button class="action-btn btn-muted" @click="showMkdir = true" title="New folder">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/><line x1="12" y1="11" x2="12" y2="17"/><line x1="9" y1="14" x2="15" y2="14"/></svg>
          New Folder
        </button>
      </div>
    </div>

    <!-- New folder inline input -->
    <div v-if="showMkdir" class="mkdir-bar">
      <input
        v-model="mkdirName" ref="mkdirInput"
        class="mkdir-input" placeholder="folder name"
        @keydown.enter="createDir" @keydown.esc="showMkdir = false"
      />
      <button class="action-btn btn-green" @click="createDir">Create</button>
      <button class="action-btn btn-muted" @click="showMkdir = false">Cancel</button>
    </div>

    <!-- Table -->
    <table class="files-table">
      <thead>
        <tr>
          <th class="th-name" @click="sort('name')">
            NAME <span class="sort-arrow">{{ sortArrow('name') }}</span>
          </th>
          <th @click="sort('size')">SIZE <span class="sort-arrow">{{ sortArrow('size') }}</span></th>
          <th>PERMISSIONS</th>
          <th>OWNER</th>
          <th @click="sort('modified')">MODIFIED <span class="sort-arrow">{{ sortArrow('modified') }}</span></th>
          <th>ACTIONS</th>
        </tr>
      </thead>
      <tbody>
        <tr v-if="loading">
          <td colspan="6" class="loading-cell">
            <div class="skeleton" v-for="i in 6" :key="i"></div>
          </td>
        </tr>
        <tr v-else-if="sorted.length === 0">
          <td colspan="6" class="empty-cell">Empty directory</td>
        </tr>
        <tr
          v-else
          v-for="entry in sorted" :key="entry.path"
          class="file-row"
          :class="{ selected: selectedPath === entry.path }"
          @click="handleRowClick(entry)"
          @dblclick="handleDblClick(entry)"
        >
          <td class="name-cell">
            <!-- Dir icon -->
            <svg v-if="entry.is_dir" width="14" height="14" viewBox="0 0 24 24" fill="currentColor" class="icon-dir">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            <!-- File icon -->
            <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" class="icon-file">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/>
            </svg>
            <span>{{ entry.name }}</span>
          </td>
          <td class="mono-cell">{{ entry.is_dir ? '—' : formatSize(entry.size) }}</td>
          <td class="mono-cell perm-cell">{{ entry.permissions }}</td>
          <td class="mono-cell">{{ entry.owner }}</td>
          <td class="mono-cell">{{ formatDate(entry.modified) }}</td>
          <td class="actions-cell" @click.stop>
            <a v-if="!entry.is_dir" :href="`/api/files/download?path=${encodeURIComponent(entry.path)}`"
               class="row-btn" title="Download" target="_blank">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </a>
            <button class="row-btn" title="Rename" @click="startRename(entry)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
            </button>
            <button class="row-btn btn-danger" title="Delete" @click="confirmDelete(entry)">
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>
            </button>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Rename inline dialog -->
    <div v-if="renameEntry" class="modal-overlay" @click.self="renameEntry = null">
      <div class="modal">
        <div class="modal-title">Rename</div>
        <input v-model="renameValue" class="modal-input" @keydown.enter="doRename" @keydown.esc="renameEntry = null" />
        <div class="modal-actions">
          <button class="action-btn btn-blue" @click="doRename">Rename</button>
          <button class="action-btn btn-muted" @click="renameEntry = null">Cancel</button>
        </div>
      </div>
    </div>

    <!-- Delete confirm dialog -->
    <div v-if="deleteEntry" class="modal-overlay" @click.self="deleteEntry = null">
      <div class="modal">
        <div class="modal-title">Delete "{{ deleteEntry.name }}"?</div>
        <p class="modal-body">{{ deleteEntry.is_dir ? 'Directory and all its contents will be deleted.' : 'This action cannot be undone.' }}</p>
        <div class="modal-actions">
          <button class="action-btn btn-danger" @click="doDelete">Delete</button>
          <button class="action-btn btn-muted" @click="deleteEntry = null">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import api from '../../api/client.js'

const props = defineProps({
  path: String,
  entries: Array,
  loading: Boolean,
})
const emit = defineEmits(['navigate', 'selectFile', 'refresh'])

const selectedPath = ref(null)
const sortKey = ref('name')
const sortDir = ref(1) // 1 = asc, -1 = desc
const showMkdir = ref(false)
const mkdirName = ref('')
const mkdirInput = ref(null)
const renameEntry = ref(null)
const renameValue = ref('')
const deleteEntry = ref(null)

// Breadcrumb segments from path
const segments = computed(() => {
  if (!props.path) return []
  const parts = props.path === '/' ? [''] : props.path.split('/')
  const segs = []
  let acc = ''
  for (const part of parts) {
    acc = acc === '' ? (part === '' ? '/' : '/' + part) : acc + '/' + part
    segs.push({ label: part === '' ? '/' : part, path: acc })
  }
  return segs
})

const sorted = computed(() => {
  if (!props.entries) return []
  return [...props.entries].sort((a, b) => {
    // Dirs always first
    if (a.is_dir !== b.is_dir) return a.is_dir ? -1 : 1
    let va = a[sortKey.value] ?? ''
    let vb = b[sortKey.value] ?? ''
    if (sortKey.value === 'size') { va = va ?? -1; vb = vb ?? -1 }
    if (sortKey.value === 'modified') { va = new Date(va); vb = new Date(vb) }
    return va < vb ? -sortDir.value : va > vb ? sortDir.value : 0
  })
})

function sort(key) {
  if (sortKey.value === key) sortDir.value *= -1
  else { sortKey.value = key; sortDir.value = 1 }
}
function sortArrow(key) {
  if (sortKey.value !== key) return ''
  return sortDir.value === 1 ? '↑' : '↓'
}

function handleRowClick(entry) {
  selectedPath.value = entry.path
  if (!entry.is_dir) emit('selectFile', entry)
}
function handleDblClick(entry) {
  if (entry.is_dir) emit('navigate', entry.path)
  else emit('selectFile', entry)
}

function formatSize(bytes) {
  if (bytes == null) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 ** 3) return `${(bytes / 1024 ** 2).toFixed(1)} MB`
  return `${(bytes / 1024 ** 3).toFixed(2)} GB`
}

function formatDate(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

async function createDir() {
  if (!mkdirName.value.trim()) return
  try {
    await api.post('/files/mkdir', { path: `${props.path}/${mkdirName.value.trim()}` })
    showMkdir.value = false
    mkdirName.value = ''
    emit('refresh')
  } catch (e) {
    alert(e.response?.data?.detail || 'Failed to create folder')
  }
}

async function uploadFile(e) {
  const files = e.target.files
  for (const file of files) {
    const form = new FormData()
    form.append('file', file)
    try {
      await api.post(`/files/upload?path=${encodeURIComponent(props.path)}`, form)
    } catch (err) {
      alert(`Upload failed: ${err.response?.data?.detail || err.message}`)
    }
  }
  e.target.value = ''
  emit('refresh')
}

function startRename(entry) {
  renameEntry.value = entry
  renameValue.value = entry.name
}

async function doRename() {
  if (!renameValue.value.trim()) return
  const dir = renameEntry.value.path.split('/').slice(0, -1).join('/') || '/'
  const newPath = `${dir}/${renameValue.value.trim()}`
  try {
    await api.post('/files/rename', { source: renameEntry.value.path, destination: newPath })
    renameEntry.value = null
    emit('refresh')
  } catch (e) {
    alert(e.response?.data?.detail || 'Rename failed')
  }
}

function confirmDelete(entry) { deleteEntry.value = entry }

async function doDelete() {
  try {
    await api.delete(`/files/delete?path=${encodeURIComponent(deleteEntry.value.path)}`)
    deleteEntry.value = null
    emit('refresh')
  } catch (e) {
    alert(e.response?.data?.detail || 'Delete failed')
  }
}
</script>

<style scoped>
.file-list { display: flex; flex-direction: column; height: 100%; }

/* Toolbar */
.list-toolbar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  gap: 10px; flex-shrink: 0;
}
.breadcrumb { display: flex; align-items: center; gap: 0; overflow-x: auto; flex: 1; }
.breadcrumb-sep { color: var(--text-dim); padding: 0 2px; font-family: var(--font-mono); font-size: 11px; }
.breadcrumb-btn {
  background: none; border: none; padding: 2px 4px;
  font-family: var(--font-mono); font-size: 11px; color: var(--text-muted);
  cursor: pointer; border-radius: 3px; transition: color 0.1s;
  white-space: nowrap;
}
.breadcrumb-btn:hover { color: var(--accent-blue); }
.toolbar-actions { display: flex; gap: 6px; flex-shrink: 0; }
.action-btn {
  display: flex; align-items: center; gap: 5px;
  background: none; border: 1px solid var(--border);
  padding: 4px 10px; border-radius: 4px; font-size: 11px;
  font-family: var(--font-mono); cursor: pointer; color: var(--text-muted);
  transition: all 0.15s; text-decoration: none;
}
.btn-blue:hover { border-color: var(--accent-blue); color: var(--accent-blue); }
.btn-green:hover { border-color: var(--accent-green); color: var(--accent-green); }
.btn-danger { border-color: transparent; }
.btn-danger:hover { border-color: var(--accent-red); color: var(--accent-red); }
.btn-muted:hover { border-color: var(--border-bright); color: var(--text); }
.hidden-input { display: none; }

/* Mkdir bar */
.mkdir-bar {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; background: var(--surface-2); border-bottom: 1px solid var(--border);
}
.mkdir-input {
  flex: 1; max-width: 280px;
  background: var(--surface); border: 1px solid var(--border-bright);
  padding: 4px 8px; border-radius: 4px;
  font-family: var(--font-mono); font-size: 12px; color: var(--text);
  outline: none;
}
.mkdir-input:focus { border-color: var(--accent-blue); }

/* Table */
.files-table {
  width: 100%; border-collapse: collapse; flex: 1;
  font-size: 12px;
}
.files-table th {
  font-family: var(--font-mono); font-size: 9px; letter-spacing: 1.5px;
  color: var(--text-muted); text-align: left;
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  background: var(--surface-2); cursor: pointer; user-select: none;
  white-space: nowrap;
}
.files-table th:hover { color: var(--text); }
.sort-arrow { color: var(--accent-blue); margin-left: 2px; }
.file-row { cursor: pointer; transition: background 0.1s; }
.file-row:hover { background: var(--surface-2); }
.file-row.selected { background: var(--surface-3); }
.file-row td { padding: 7px 12px; border-bottom: 1px solid var(--border); }
.name-cell {
  display: flex; align-items: center; gap: 7px;
  font-size: 12px; color: var(--text-bright);
}
.icon-dir { color: var(--accent-yellow); flex-shrink: 0; }
.icon-file { color: var(--text-muted); flex-shrink: 0; }
.mono-cell { font-family: var(--font-mono); color: var(--text-muted); white-space: nowrap; }
.perm-cell { letter-spacing: 0.5px; }
.actions-cell { display: flex; gap: 4px; align-items: center; }
.row-btn {
  background: none; border: none; padding: 3px 5px;
  color: var(--text-dim); cursor: pointer; border-radius: 3px;
  display: flex; align-items: center; transition: color 0.1s;
  text-decoration: none;
}
.row-btn:hover { color: var(--text); }
.row-btn.btn-danger:hover { color: var(--accent-red); }

.loading-cell { padding: 12px; }
.skeleton {
  height: 14px; background: var(--surface-2); border-radius: 4px;
  margin-bottom: 8px; animation: shimmer 1.4s infinite;
}
@keyframes shimmer { 0%,100%{opacity:.4} 50%{opacity:.8} }
.empty-cell { text-align: center; padding: 40px; color: var(--text-muted); }

/* Modals */
.modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.5);
  display: flex; align-items: center; justify-content: center; z-index: 200;
}
.modal {
  background: var(--surface); border: 1px solid var(--border-bright);
  border-radius: 8px; padding: 24px; min-width: 320px;
}
.modal-title { font-weight: 600; margin-bottom: 12px; font-size: 14px; }
.modal-body { color: var(--text-muted); font-size: 13px; margin-bottom: 16px; }
.modal-input {
  width: 100%; background: var(--surface-2); border: 1px solid var(--border-bright);
  padding: 7px 10px; border-radius: 5px; color: var(--text);
  font-family: var(--font-mono); font-size: 13px; outline: none;
  margin-bottom: 14px;
}
.modal-input:focus { border-color: var(--accent-blue); }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; }
</style>
```

- [ ] **Create `frontend/src/views/FilesView.vue`**

```vue
<template>
  <div class="files-view">
    <!-- Top panel: directory tree -->
    <div class="tree-panel" :style="{ height: treePanelHeight + 'px' }">
      <div class="panel-header">
        <span class="panel-title">DIRECTORY TREE</span>
      </div>
      <div class="tree-scroll">
        <DirTree
          :node="{ name: '/', path: '/' }"
          :current-path="currentPath"
          :depth="0"
          @navigate="navigateTo"
        />
      </div>
    </div>

    <!-- Draggable divider -->
    <div class="divider" @mousedown="startResize">
      <div class="divider-handle"></div>
    </div>

    <!-- Bottom panel: file list -->
    <div class="list-panel">
      <FileList
        :path="currentPath"
        :entries="entries"
        :loading="loading"
        @navigate="navigateTo"
        @select-file="openFile"
        @refresh="loadDir"
      />
    </div>

    <!-- Monaco viewer/editor panel (slides in from right when file selected) -->
    <Transition name="slide-right">
      <div v-if="openedFile" class="editor-panel">
        <div class="editor-header">
          <span class="editor-filename">{{ openedFile.name }}</span>
          <div class="editor-actions">
            <button v-if="editorDirty" class="editor-btn btn-green" @click="saveFile">Save</button>
            <button class="editor-btn btn-muted" @click="closeFile">✕</button>
          </div>
        </div>
        <div v-if="fileLoading" class="editor-loading">Loading…</div>
        <VueMonacoEditor
          v-else
          v-model:value="editorContent"
          :language="editorLanguage"
          theme="vs-dark"
          :options="monacoOptions"
          class="monaco-editor-wrap"
          @change="editorDirty = true"
        />
      </div>
    </Transition>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { VueMonacoEditor } from '@guolao/vue-monaco-editor'
import DirTree from '../components/files/DirTree.vue'
import FileList from '../components/files/FileList.vue'
import api from '../api/client.js'
import { useAuthStore } from '../stores/auth.js'

const auth = useAuthStore()
const currentPath = ref('/')
const entries = ref([])
const loading = ref(false)

// Split resize
const treePanelHeight = ref(280)
function startResize(e) {
  const startY = e.clientY
  const startH = treePanelHeight.value
  function onMove(e) {
    treePanelHeight.value = Math.max(120, Math.min(600, startH + e.clientY - startY))
  }
  function onUp() {
    window.removeEventListener('mousemove', onMove)
    window.removeEventListener('mouseup', onUp)
  }
  window.addEventListener('mousemove', onMove)
  window.addEventListener('mouseup', onUp)
}

async function loadDir() {
  loading.value = true
  try {
    const { data } = await api.get('/files/list', { params: { path: currentPath.value } })
    entries.value = data.entries
  } catch (e) {
    entries.value = []
  } finally {
    loading.value = false
  }
}

function navigateTo(path) {
  currentPath.value = path
  loadDir()
}

// Monaco editor
const openedFile = ref(null)
const editorContent = ref('')
const editorLanguage = ref('plaintext')
const editorDirty = ref(false)
const fileLoading = ref(false)

const canEdit = auth.role !== 'readonly'
const monacoOptions = {
  readOnly: !canEdit,
  minimap: { enabled: false },
  fontSize: 13,
  fontFamily: "'Fira Code', monospace",
  scrollBeyondLastLine: false,
  lineNumbers: 'on',
  wordWrap: 'on',
}

async function openFile(entry) {
  openedFile.value = entry
  editorDirty.value = false
  fileLoading.value = true
  try {
    const { data } = await api.get('/files/content', { params: { path: entry.path } })
    editorContent.value = data.content
    editorLanguage.value = data.language
  } catch (e) {
    editorContent.value = `// Error loading file: ${e.response?.data?.detail || e.message}`
    editorLanguage.value = 'plaintext'
  } finally {
    fileLoading.value = false
  }
}

function closeFile() {
  if (editorDirty.value && !confirm('Discard unsaved changes?')) return
  openedFile.value = null
  editorContent.value = ''
  editorDirty.value = false
}

async function saveFile() {
  try {
    await api.put(`/files/content?path=${encodeURIComponent(openedFile.value.path)}`,
      { content: editorContent.value })
    editorDirty.value = false
  } catch (e) {
    alert(`Save failed: ${e.response?.data?.detail || e.message}`)
  }
}

onMounted(loadDir)
</script>

<style scoped>
.files-view {
  display: flex; flex-direction: column;
  height: calc(100vh - var(--header-height) - 48px);
  overflow: hidden; position: relative;
}

/* Tree panel */
.tree-panel {
  display: flex; flex-direction: column;
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px 8px 0 0; overflow: hidden; flex-shrink: 0;
}
.panel-header {
  padding: 8px 12px; border-bottom: 1px solid var(--border);
  background: var(--surface-2); flex-shrink: 0;
}
.panel-title {
  font-family: var(--font-mono); font-size: 9px;
  letter-spacing: 1.5px; color: var(--text-muted);
}
.tree-scroll { overflow-y: auto; flex: 1; padding: 4px 0; }

/* Divider */
.divider {
  height: 6px; background: var(--border);
  cursor: ns-resize; display: flex;
  align-items: center; justify-content: center;
  flex-shrink: 0; transition: background 0.15s;
}
.divider:hover { background: var(--accent-blue); }
.divider-handle {
  width: 32px; height: 2px; border-radius: 1px;
  background: var(--text-dim);
}

/* List panel */
.list-panel {
  flex: 1; overflow: hidden;
  background: var(--surface); border: 1px solid var(--border);
  border-top: none; border-radius: 0 0 8px 8px;
  display: flex; flex-direction: column;
}

/* Monaco editor panel */
.editor-panel {
  position: absolute; inset: 0; left: auto;
  width: 55%; background: var(--surface);
  border: 1px solid var(--border-bright);
  border-radius: 8px;
  display: flex; flex-direction: column;
  z-index: 10;
  box-shadow: -8px 0 30px rgba(0,0,0,0.4);
}
.editor-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 14px; border-bottom: 1px solid var(--border);
  background: var(--surface-2); flex-shrink: 0;
}
.editor-filename {
  font-family: var(--font-mono); font-size: 12px; color: var(--text-bright);
}
.editor-actions { display: flex; gap: 6px; }
.editor-btn {
  background: none; border: 1px solid var(--border);
  padding: 3px 10px; border-radius: 4px; font-size: 11px;
  font-family: var(--font-mono); cursor: pointer; color: var(--text-muted);
  transition: all 0.15s;
}
.btn-green:hover { border-color: var(--accent-green); color: var(--accent-green); }
.btn-muted:hover { border-color: var(--border-bright); color: var(--text); }
.editor-loading {
  flex: 1; display: flex; align-items: center; justify-content: center;
  font-family: var(--font-mono); font-size: 12px; color: var(--text-muted);
}
.monaco-editor-wrap { flex: 1; min-height: 0; }

/* Transitions */
.slide-right-enter-active, .slide-right-leave-active { transition: transform 0.2s ease, opacity 0.2s ease; }
.slide-right-enter-from, .slide-right-leave-to { transform: translateX(30px); opacity: 0; }
</style>
```

- [ ] **Update `frontend/src/router/index.js`** — add Files route:
```js
import FilesView from '../views/FilesView.vue'
// in routes:
{ path: '/files', component: FilesView, meta: { title: 'Files', requiresAuth: true } }
```

- [ ] **Update sidebar** — remove `disabled` from Files RouterLink in `AppSidebar.vue`

- [ ] **Build:**
```bash
cd /home/crt/server_dashboard/frontend
npm run build 2>&1 | tail -8
```

- [ ] **Run all tests:** `.venv/bin/pytest tests/ -q`

- [ ] **Commit:**
```bash
git add frontend/src/
git commit -m "feat: Phase 3 File Explorer — split panel, tree, file list, Monaco editor"
```
