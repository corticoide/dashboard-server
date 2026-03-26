from pydantic import BaseModel
from typing import List, Optional

class FileEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    permissions: str
    owner: str
    group: str
    modified: str

class DirListing(BaseModel):
    path: str
    parent: Optional[str] = None
    entries: List[FileEntry]

class FileContent(BaseModel):
    path: str
    content: str
    size: int
    language: str

class MkdirRequest(BaseModel):
    path: str

class RenameRequest(BaseModel):
    source: str
    destination: str

class FileWriteRequest(BaseModel):
    content: str
