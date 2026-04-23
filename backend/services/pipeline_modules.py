"""Native pipeline modules. Each function returns (exit_code: int, output: str)."""
import shutil
import tarfile
import zipfile
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Tuple


def move_file(config: dict, context: dict) -> Tuple[int, str]:
    """Move a file or directory from src to dst."""
    src, dst = config["src"], config["dst"]
    try:
        shutil.move(src, dst)
        return 0, f"Moved {src} → {dst}"
    except Exception as e:
        return 1, f"Error moving {src}: {e}"


def copy_file(config: dict, context: dict) -> Tuple[int, str]:
    """Copy a file or directory from src to dst."""
    src, dst = config["src"], config["dst"]
    try:
        if Path(src).is_dir():
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
        return 0, f"Copied {src} → {dst}"
    except Exception as e:
        return 1, f"Error copying {src}: {e}"


def delete_file(config: dict, context: dict) -> Tuple[int, str]:
    """Delete a file or directory."""
    path = config["path"]
    try:
        p = Path(path)
        if p.is_dir():
            shutil.rmtree(path)
        else:
            p.unlink()
        return 0, f"Deleted {path}"
    except Exception as e:
        return 1, f"Error deleting {path}: {e}"


def mkdir(config: dict, context: dict) -> Tuple[int, str]:
    """Create a directory with parents (recursive)."""
    path = config["path"]
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return 0, f"Created {path}"
    except Exception as e:
        return 1, f"Error creating {path}: {e}"


def write_file(config: dict, context: dict) -> Tuple[int, str]:
    """Write content to a file in overwrite or append mode."""
    path, content = config["path"], config.get("content", "")
    mode = config.get("mode", "overwrite")
    try:
        with open(path, "a" if mode == "append" else "w", encoding="utf-8") as f:
            f.write(content)
        return 0, f"Written to {path} (mode={mode})"
    except Exception as e:
        return 1, f"Error writing {path}: {e}"


def rename_file(config: dict, context: dict) -> Tuple[int, str]:
    """Rename a file, optionally with timestamp prefix."""
    from datetime import timezone
    path, new_name = config["path"], config["new_name"]
    use_timestamp = config.get("use_timestamp", False)
    try:
        p = Path(path)
        if use_timestamp:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            new_name = f"{ts}_{new_name}"
        p.rename(p.parent / new_name)
        return 0, f"Renamed {path} → {p.parent / new_name}"
    except Exception as e:
        return 1, f"Error renaming {path}: {e}"


def compress(config: dict, context: dict) -> Tuple[int, str]:
    """Compress a file or directory to tar.gz or zip format."""
    src, dst, fmt = config["src"], config["dst"], config.get("format", "tar.gz")
    try:
        if fmt == "tar.gz":
            with tarfile.open(dst, "w:gz") as tar:
                tar.add(src, arcname=Path(src).name)
        elif fmt == "zip":
            with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
                p = Path(src)
                if p.is_dir():
                    for f in p.rglob("*"):
                        zf.write(f, f.relative_to(p.parent))
                else:
                    zf.write(src, p.name)
        else:
            return 1, f"Unknown format: {fmt}"
        return 0, f"Compressed {src} → {dst}"
    except Exception as e:
        return 1, f"Error compressing: {e}"


def decompress(config: dict, context: dict) -> Tuple[int, str]:
    """Decompress a tar.gz or zip archive."""
    src, dst = config["src"], config["dst"]
    try:
        if src.endswith((".tar.gz", ".tgz")):
            with tarfile.open(src, "r:gz") as tar:
                tar.extractall(dst)
        elif src.endswith(".zip"):
            with zipfile.ZipFile(src, "r") as zf:
                zf.extractall(dst)
        else:
            return 1, f"Unknown archive: {src}"
        return 0, f"Decompressed {src} → {dst}"
    except Exception as e:
        return 1, f"Error decompressing: {e}"


def check_exists(config: dict, context: dict) -> Tuple[int, str]:
    """Check if a file or directory exists."""
    path, check_type = config["path"], config.get("type", "any")
    p = Path(path)
    exists = p.is_file() if check_type == "file" else p.is_dir() if check_type == "dir" else p.exists()
    return (0, f"Exists: {path}") if exists else (1, f"Not found ({check_type}): {path}")


def delay(config: dict, context: dict) -> Tuple[int, str]:
    """Sleep for a given number of seconds."""
    seconds = float(config.get("seconds", 1))
    time.sleep(seconds)
    return 0, f"Waited {seconds}s"


def log_message(config: dict, context: dict) -> Tuple[int, str]:
    """Log a message with a given level."""
    message = config.get("message", "")
    level = config.get("level", "info").upper()
    return 0, f"[{level}] {message}"


def load_env(config: dict, context: dict) -> Tuple[int, str]:
    """Load environment variables from a .env file into the context."""
    path = config["path"]
    try:
        loaded = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                context[key.strip()] = val.strip()
                loaded.append(key.strip())
        return 0, f"Loaded {len(loaded)} vars from {path}"
    except Exception as e:
        return 1, f"Error loading .env {path}: {e}"


def send_email(config: dict, context: dict) -> Tuple[int, str]:
    """Send an email message (requires SMTP configuration in settings)."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders
    from backend.config import settings

    smtp_host = getattr(settings, "smtp_host", "")
    if not smtp_host:
        return 1, "SMTP not configured: set SMTP_HOST in .env"

    to = config["to"]
    subject = config.get("subject", "Pipeline notification")
    body = config.get("body", "")
    attachment = config.get("attachment")
    try:
        msg = MIMEMultipart()
        msg["From"] = settings.smtp_from
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(body, "plain"))
        if attachment and Path(attachment).exists():
            with open(attachment, "rb") as f:
                part = MIMEBase("application", "octet-stream")
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f"attachment; filename={Path(attachment).name}")
            msg.attach(part)
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port) as server:
            server.starttls()
            server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(settings.smtp_from, to, msg.as_string())
        return 0, f"Email sent to {to}"
    except Exception as e:
        return 1, f"Error sending email: {e}"


# Module registry for dynamic loading
MODULE_REGISTRY = {
    "move_file": move_file,
    "copy_file": copy_file,
    "delete_file": delete_file,
    "mkdir": mkdir,
    "write_file": write_file,
    "rename_file": rename_file,
    "compress": compress,
    "decompress": decompress,
    "check_exists": check_exists,
    "delay": delay,
    "log": log_message,
    "load_env": load_env,
    "email": send_email,
    # "call_pipeline" handled in pipeline_service to avoid circular import
}
