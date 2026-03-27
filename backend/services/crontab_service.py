# TODO: migrate to python-crontab library (already in requirements.txt)
import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

from backend.schemas.crontab import CrontabEntry, CrontabEntryCreate

# Absolute path to the logging wrapper so cron (minimal PATH) can find it.
# Use the venv Python if available (same interpreter the server runs under).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_VENV_PYTHON = _PROJECT_ROOT / ".venv" / "bin" / "python3"
_PYTHON = str(_VENV_PYTHON) if _VENV_PYTHON.exists() else sys.executable
_WRAPPER = str(Path(__file__).resolve().parent.parent / "scripts" / "cron_log.py")
_WRAPPER_PREFIX = f"{_PYTHON} {_WRAPPER} "

SPECIAL_STRINGS = {
    "@reboot", "@yearly", "@annually", "@monthly",
    "@weekly", "@daily", "@midnight", "@hourly",
}

# Regex: 5 cron fields + at least one command token
_CRON_RE = re.compile(
    r'^(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.+)$'
)
# Very basic cron field validation (allows *, numbers, /, -, ,)
_FIELD_RE = re.compile(r'^[\d\*\/\-\,]+$')


def _run(args: List[str], stdin: Optional[str] = None) -> Tuple[str, str, int]:
    proc = subprocess.run(
        ["crontab"] + args,
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return proc.stdout, proc.stderr, proc.returncode


def _load_raw() -> str:
    stdout, stderr, rc = _run(["-l"])
    if rc != 0:
        if "no crontab for" in stderr.lower():
            return ""
        raise RuntimeError(stderr.strip() or "Failed to read crontab")
    return stdout


def _parse_raw(text: str) -> List[CrontabEntry]:
    entries: List[CrontabEntry] = []
    pending_comment: Optional[str] = None
    logical_idx = 0

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            pending_comment = None
            continue

        # Comment line — save for the next job
        if stripped.startswith("#"):
            # Ignore meta-comments from crontab -l header
            if stripped.startswith("# DO NOT EDIT") or stripped.startswith("# ("):
                continue
            pending_comment = stripped[1:].strip()
            continue

        # Skip environment variable assignments (VAR=value)
        if re.match(r'^[A-Z_][A-Z0-9_]*\s*=', stripped):
            pending_comment = None
            continue

        # Special string (@reboot, @daily, …)
        if stripped.startswith("@"):
            parts = stripped.split(None, 1)
            special = parts[0].lower()
            if special in SPECIAL_STRINGS:
                entries.append(CrontabEntry(
                    id=logical_idx,
                    minute="", hour="", dom="", month="", dow="",
                    command=parts[1] if len(parts) > 1 else "",
                    comment=pending_comment,
                    is_special=True,
                    special=parts[0],
                    raw=line,
                ))
                logical_idx += 1
            pending_comment = None
            continue

        # Standard 5-field entry
        m = _CRON_RE.match(stripped)
        if m:
            entries.append(CrontabEntry(
                id=logical_idx,
                minute=m.group(1),
                hour=m.group(2),
                dom=m.group(3),
                month=m.group(4),
                dow=m.group(5),
                command=m.group(6),
                comment=pending_comment,
                is_special=False,
                special=None,
                raw=line,
            ))
            logical_idx += 1

        pending_comment = None

    return entries


def _entries_to_text(entries: List[CrontabEntry]) -> str:
    lines: List[str] = []
    for e in entries:
        if e.comment:
            lines.append(f"# {e.comment}")
        if e.is_special and e.special:
            lines.append(f"{e.special} {e.command}")
        else:
            lines.append(f"{e.minute} {e.hour} {e.dom} {e.month} {e.dow} {e.command}")
    lines.append("")  # trailing newline
    return "\n".join(lines)


def _save(entries: List[CrontabEntry]) -> None:
    text = _entries_to_text(entries)
    _, stderr, rc = _run(["-"], stdin=text)
    if rc != 0:
        raise RuntimeError(stderr.strip() or "Failed to save crontab")


def validate_field(value: str, name: str) -> None:
    """Raise ValueError if a cron field is syntactically invalid."""
    if value == "*":
        return
    # Split on comma for list values, validate each part
    for part in value.split(","):
        # Handle step: */N or range/N
        step_parts = part.split("/")
        if len(step_parts) > 2:
            raise ValueError(f"Invalid {name} field: {value!r}")
        base = step_parts[0]
        if len(step_parts) == 2:
            if not step_parts[1].isdigit():
                raise ValueError(f"Invalid step in {name}: {value!r}")
        # Range: N-M or *
        if "-" in base:
            rng = base.split("-")
            if len(rng) != 2 or not rng[0].isdigit() or not rng[1].isdigit():
                raise ValueError(f"Invalid range in {name}: {value!r}")
        elif base != "*" and not base.isdigit():
            raise ValueError(f"Invalid {name} value: {value!r}")


# ── Wrapper helpers ───────────────────────────────────────────────────────────

def _is_wrapped(cmd: str) -> bool:
    """Return True if the command is already wrapped by cron_log.py."""
    return _WRAPPER in cmd


def _wrap_command(cmd: str) -> str:
    """Prepend the logging wrapper unless the command is already wrapped."""
    cmd = cmd.strip()
    if _is_wrapped(cmd):
        return cmd
    return f"{_WRAPPER_PREFIX}{cmd}"


def _unwrap_command(cmd: str) -> str:
    """Strip the logging wrapper prefix so the UI shows the raw command."""
    if cmd.startswith(_WRAPPER_PREFIX):
        return cmd[len(_WRAPPER_PREFIX):]
    return cmd


def _strip_wrapper_from_entries(entries: List[CrontabEntry]) -> List[CrontabEntry]:
    """Return entries with wrapper stripped from command (for display)."""
    for e in entries:
        e.command = _unwrap_command(e.command)
    return entries


# ── Public API ────────────────────────────────────────────────────────────────

def list_entries() -> List[CrontabEntry]:
    return _strip_wrapper_from_entries(_parse_raw(_load_raw()))


def add_entry(data: CrontabEntryCreate) -> List[CrontabEntry]:
    entries = _parse_raw(_load_raw())
    new_id = max((e.id for e in entries), default=-1) + 1
    new_entry = CrontabEntry(
        id=new_id,
        minute=data.minute,
        hour=data.hour,
        dom=data.dom,
        month=data.month,
        dow=data.dow,
        command=_wrap_command(data.command),
        comment=data.comment,
        is_special=data.is_special,
        special=data.special,
        raw="",
    )
    entries.append(new_entry)
    _save(entries)
    return _strip_wrapper_from_entries(_parse_raw(_load_raw()))


def update_entry(entry_id: int, data: CrontabEntryCreate) -> List[CrontabEntry]:
    entries = _parse_raw(_load_raw())
    idx = next((i for i, e in enumerate(entries) if e.id == entry_id), None)
    if idx is None:
        raise ValueError(f"Entry {entry_id} not found")
    entries[idx] = CrontabEntry(
        id=entry_id,
        minute=data.minute,
        hour=data.hour,
        dom=data.dom,
        month=data.month,
        dow=data.dow,
        command=_wrap_command(data.command),
        comment=data.comment,
        is_special=data.is_special,
        special=data.special,
        raw="",
    )
    _save(entries)
    return _strip_wrapper_from_entries(_parse_raw(_load_raw()))


def delete_entry(entry_id: int) -> List[CrontabEntry]:
    entries = _parse_raw(_load_raw())
    before = len(entries)
    entries = [e for e in entries if e.id != entry_id]
    if len(entries) == before:
        raise ValueError(f"Entry {entry_id} not found")
    _save(entries)
    return _strip_wrapper_from_entries(_parse_raw(_load_raw()))
