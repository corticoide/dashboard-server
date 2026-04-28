import smtplib
import subprocess
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy.orm import Session

from backend.models.system_setting import SystemSetting

DEFAULTS: dict[str, str] = {
    "log_retention_days":     "30",
    "metrics_retention_days": "30",
    "network_retention_days": "30",
    "alerts_retention_days":  "90",
    "smtp_host":              "",
    "smtp_port":              "587",
    "smtp_user":              "",
    "smtp_password":          "",
    "smtp_from":              "",
}

_tz_cache: list[str] | None = None


def get_setting(db: Session, key: str, default: str | None = None) -> str:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is not None:
        return row.value
    return default if default is not None else DEFAULTS.get(key, "")


def get_all_settings(db: Session) -> dict[str, str]:
    rows = {r.key: r.value for r in db.query(SystemSetting).all()}
    return {k: rows.get(k, v) for k, v in DEFAULTS.items()}


def upsert_setting(db: Session, key: str, value: str) -> None:
    row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if row is not None:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))


def upsert_settings(db: Session, updates: dict[str, str]) -> None:
    for key, value in updates.items():
        if key in DEFAULTS:
            upsert_setting(db, key, value)
    db.commit()


def seed_defaults(db: Session) -> None:
    for key, value in DEFAULTS.items():
        if not db.query(SystemSetting).filter(SystemSetting.key == key).first():
            db.add(SystemSetting(key=key, value=value))
    db.commit()


def get_system_timezone() -> str:
    try:
        result = subprocess.run(
            ["timedatectl", "show", "--property=Timezone", "--value"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    try:
        with open("/etc/timezone") as f:
            return f.read().strip()
    except OSError:
        return "UTC"


def list_timezones() -> list[str]:
    global _tz_cache
    if _tz_cache is not None:
        return _tz_cache
    try:
        from zoneinfo import available_timezones
        _tz_cache = sorted(available_timezones())
    except ImportError:
        try:
            result = subprocess.run(
                ["timedatectl", "list-timezones"],
                capture_output=True, text=True, timeout=10,
            )
            _tz_cache = sorted(result.stdout.strip().splitlines())
        except (FileNotFoundError, subprocess.TimeoutExpired):
            _tz_cache = ["UTC"]
    return _tz_cache


def set_system_timezone(tz_name: str) -> tuple[bool, str]:
    valid = set(list_timezones())
    if tz_name not in valid:
        return False, f"Unknown timezone: {tz_name}"
    try:
        result = subprocess.run(
            ["timedatectl", "set-timezone", tz_name],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            return True, ""
        return False, result.stderr.strip() or f"timedatectl exited with code {result.returncode}"
    except FileNotFoundError:
        return False, "timedatectl not found — cannot change timezone on this system"
    except subprocess.TimeoutExpired:
        return False, "timedatectl timed out"


def test_smtp(
    host: str, port: int, user: str, password: str, from_addr: str, to_addr: str
) -> tuple[bool, str]:
    if not host:
        return False, "SMTP host is required"
    try:
        msg = MIMEMultipart()
        msg["From"] = from_addr
        msg["To"] = to_addr
        msg["Subject"] = "ServerDash — SMTP Test"
        msg.attach(MIMEText(
            "This is a test email from ServerDash to verify SMTP configuration.", "plain"
        ))
        with smtplib.SMTP(host, port, timeout=10) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.sendmail(from_addr, [to_addr], msg.as_string())
        return True, ""
    except smtplib.SMTPAuthenticationError as e:
        return False, f"Authentication failed: {e}"
    except smtplib.SMTPConnectError as e:
        return False, f"Connection refused: {e}"
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {e}"
    except OSError as e:
        return False, f"Network error: {e}"
