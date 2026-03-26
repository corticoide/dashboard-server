import logging
import os
from logging.handlers import TimedRotatingFileHandler

_initialized = False


def _ensure_data_dir() -> str:
    data_dir = os.path.join(os.path.dirname(__file__), "..", "..", "data")
    data_dir = os.path.normpath(data_dir)
    os.makedirs(data_dir, exist_ok=True)
    return data_dir


def init_logging() -> None:
    """Configure audit and error loggers. Safe to call multiple times."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    data_dir = _ensure_data_dir()

    # ── Audit logger ──────────────────────────────────────────────────────────
    audit_logger = logging.getLogger("serverdash.audit")
    audit_logger.setLevel(logging.INFO)
    if not audit_logger.handlers:
        handler = TimedRotatingFileHandler(
            filename=os.path.join(data_dir, "audit.log"),
            when="midnight",
            interval=1,
            backupCount=30,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        audit_logger.addHandler(handler)
    audit_logger.propagate = False

    # ── Error logger ──────────────────────────────────────────────────────────
    error_logger = logging.getLogger("serverdash.errors")
    error_logger.setLevel(logging.ERROR)
    if not error_logger.handlers:
        handler = logging.FileHandler(
            filename=os.path.join(data_dir, "errors.log"),
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        error_logger.addHandler(handler)
    error_logger.propagate = False


def get_audit_logger() -> logging.Logger:
    return logging.getLogger("serverdash.audit")


def get_error_logger() -> logging.Logger:
    return logging.getLogger("serverdash.errors")
