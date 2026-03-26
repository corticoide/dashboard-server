import os
import shutil
import subprocess
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict

from backend.database import SessionLocal
from backend.schemas.scripts import FavoriteOut

# ── Runner detection ──────────────────────────────────────────────────────────

ALLOWED_RUNNERS = {
    "python3", "python2", "bash", "sh", "zsh", "node", "ruby",
    "perl", "php", "lua", "Rscript", "tclsh", "pwsh", "ts-node",
}

EXTENSION_RUNNERS: Dict[str, str] = {
    ".py":   "python3",
    ".sh":   "bash",
    ".bash": "bash",
    ".zsh":  "zsh",
    ".rb":   "ruby",
    ".pl":   "perl",
    ".js":   "node",
    ".ts":   "ts-node",
    ".php":  "php",
    ".r":    "Rscript",
    ".lua":  "lua",
    ".ps1":  "pwsh",
    ".tcl":  "tclsh",
    ".awk":  "awk -f",
}

SHEBANG_MAP: Dict[str, str] = {
    "python":   "python3",
    "python3":  "python3",
    "python2":  "python2",
    "bash":     "bash",
    "sh":       "sh",
    "zsh":      "zsh",
    "node":     "node",
    "nodejs":   "node",
    "ruby":     "ruby",
    "perl":     "perl",
    "perl5":    "perl",
    "php":      "php",
    "lua":      "lua",
    "rscript":  "Rscript",
    "tclsh":    "tclsh",
}


def detect_runner(path: Path) -> str:
    """Detect the appropriate interpreter for a script file.

    Raises ValueError if the detected runner is not in ALLOWED_RUNNERS.
    Direct executable paths (no runner needed) are allowed as-is.
    """
    # 1. Extension-based
    ext = path.suffix.lower()
    if ext in EXTENSION_RUNNERS:
        runner = EXTENSION_RUNNERS[ext]
        # "awk -f" — base command is the first token
        base = runner.split()[0]
        if base not in ALLOWED_RUNNERS:
            raise ValueError(f"Runner not allowed: {runner}")
        return runner

    # 2. Shebang-based
    try:
        with open(path, "rb") as f:
            first_bytes = f.read(256)
        first_line = first_bytes.split(b"\n")[0].decode("utf-8", errors="replace").strip()
        if first_line.startswith("#!"):
            parts = first_line[2:].strip().split()
            if parts:
                # /usr/bin/env python3  → interpreter = python3
                # /usr/bin/python3      → interpreter = python3
                interpreter = Path(parts[-1]).name.lower()
                for key, runner in SHEBANG_MAP.items():
                    if interpreter == key:
                        if runner not in ALLOWED_RUNNERS:
                            raise ValueError(f"Runner not allowed: {runner}")
                        return runner
                # Unknown shebang interpreter — reject if not in whitelist
                detected = Path(parts[-1]).name
                if detected not in ALLOWED_RUNNERS:
                    raise ValueError(f"Runner not allowed: {detected}")
                return detected
    except (IOError, OSError):
        pass

    # 3. Executable binary (no extension, no shebang) — run directly, no runner needed
    if path.exists() and os.access(path, os.X_OK):
        return str(path)

    return "bash"


def build_favorite_out(fav) -> FavoriteOut:
    """Enrich a DB ScriptFavorite with dynamic fields."""
    p = Path(fav.path)
    exists = p.exists() and p.is_file()
    runner = detect_runner(p) if exists else "unknown"
    return FavoriteOut(
        id=fav.id,
        path=fav.path,
        run_as_root=fav.run_as_root,
        admin_only=fav.admin_only,
        runner=runner,
        exists=exists,
    )


# ── Execution engine ──────────────────────────────────────────────────────────

# Live execution state keyed by execution id
_running: Dict[int, dict] = {}


def get_poll_state(exec_id: int) -> Optional[dict]:
    return _running.get(exec_id)


def _build_cmd(path: str, runner: str, args: List[str], run_as_root: bool) -> List[str]:
    """Build the subprocess command list."""
    # Direct executable
    if runner == path:
        cmd = [path] + args
    elif " -f" in runner:
        # e.g. "awk -f" needs splitting
        cmd = runner.split() + [path] + args
    else:
        cmd = [runner, path] + args

    if run_as_root:
        cmd = ["sudo", "-S"] + cmd

    return cmd


def _reader(stream, lines: list) -> None:
    """Thread target: read lines from a stream into a list."""
    try:
        for line in stream:
            lines.append(line.rstrip("\n"))
    except ValueError:
        pass  # Stream closed


def launch_execution(
    exec_id: int,
    script_path: str,
    runner: str,
    run_as_root: bool,
    sudo_password: Optional[str],
    args: List[str],
    triggered_by: str,
) -> None:
    """Start the script execution in a background thread."""
    state: dict = {"lines": [], "running": True, "exit_code": None}
    _running[exec_id] = state

    def _run():
        cmd = _build_cmd(script_path, runner, args, run_as_root)

        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE if (run_as_root and sudo_password) else None,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                cwd=str(Path(script_path).parent),
            )

            # Feed sudo password — sudo -S reads first line from stdin, then
            # closes to child process (which receives EOF on stdin)
            if run_as_root and sudo_password and proc.stdin:
                proc.stdin.write(sudo_password + "\n")
                proc.stdin.flush()
                proc.stdin.close()

            # Read stdout and stderr concurrently
            t_err = threading.Thread(target=_reader, args=(proc.stderr, state["lines"]))
            t_err.daemon = True
            t_err.start()

            _reader(proc.stdout, state["lines"])
            t_err.join(timeout=5)

            proc.wait(timeout=300)
            exit_code = proc.returncode

            # Detect sudo auth failure
            combined = "\n".join(state["lines"]).lower()
            if (
                run_as_root
                and exit_code != 0
                and ("incorrect password" in combined or "authentication failure" in combined)
            ):
                state["lines"] = ["[sudo] Error: Incorrect password"]
                exit_code = 1

        except FileNotFoundError:
            runner_name = cmd[0] if not run_as_root else cmd[2]
            state["lines"].append(f"Error: '{runner_name}' not found — is it installed?")
            exit_code = 127
        except subprocess.TimeoutExpired:
            proc.kill()
            state["lines"].append("[Execution timed out after 5 minutes]")
            exit_code = -1
        except Exception as e:
            state["lines"].append(f"Error: {e}")
            exit_code = 1

        state["running"] = False
        state["exit_code"] = exit_code

        # Persist to DB
        ended = datetime.now(timezone.utc)
        db = SessionLocal()
        try:
            from backend.models.script import ScriptExecution
            from backend.models.execution_log import ExecutionLog
            exe = db.query(ScriptExecution).filter(ScriptExecution.id == exec_id).first()
            if exe:
                exe.ended_at = ended
                exe.exit_code = exit_code
                exe.output = "\n".join(state["lines"])
                duration = (ended - exe.started_at.replace(tzinfo=timezone.utc)).total_seconds() if exe.started_at else None
                full_output = "\n".join(state["lines"])
                log = ExecutionLog(
                    script_path=script_path,
                    username=triggered_by,
                    started_at=exe.started_at,
                    ended_at=ended,
                    exit_code=exit_code,
                    duration_seconds=duration,
                    output_summary=full_output[:500] if full_output else None,
                )
                db.add(log)
                db.commit()
        finally:
            db.close()

        # Keep state in memory for 5 minutes after completion
        threading.Timer(300, lambda: _running.pop(exec_id, None)).start()

    t = threading.Thread(target=_run, daemon=True)
    t.start()
