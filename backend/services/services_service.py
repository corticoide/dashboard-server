import re
import subprocess
from typing import List
from backend.schemas.services import ServiceInfo, ServiceLog

ALLOWED_ACTIONS = {"start", "stop", "restart", "reload"}


def parse_service_line(line: str) -> dict:
    """Parse one line from systemctl list-units output."""
    parts = line.split(None, 4)
    if len(parts) < 4:
        return {}
    return {
        "name": parts[0],
        "load_state": parts[1],
        "active_state": parts[2],
        "sub_state": parts[3],
        "description": parts[4] if len(parts) > 4 else "",
    }


def _get_enabled_map() -> dict:
    try:
        result = subprocess.run(
            ["systemctl", "list-unit-files", "--type=service", "--no-pager", "--no-legend"],
            capture_output=True, text=True, timeout=10
        )
        mapping = {}
        for line in result.stdout.splitlines():
            parts = line.split(None, 2)
            if len(parts) >= 2:
                mapping[parts[0]] = parts[1]
        return mapping
    except Exception:
        return {}


def list_services() -> List[ServiceInfo]:
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all",
             "--no-pager", "--no-legend", "--plain"],
            capture_output=True, text=True, timeout=15
        )
    except FileNotFoundError:
        raise RuntimeError("systemctl not found — systemd is not available on this system")

    enabled_map = _get_enabled_map()
    services = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parsed = parse_service_line(line)
        if not parsed or not parsed["name"].endswith(".service"):
            continue
        services.append(ServiceInfo(
            name=parsed["name"],
            load_state=parsed["load_state"],
            active_state=parsed["active_state"],
            sub_state=parsed["sub_state"],
            description=parsed["description"],
            enabled=enabled_map.get(parsed["name"], "unknown"),
        ))
    return services


def get_service_logs(name: str, lines: int = 100) -> ServiceLog:
    _validate_service_name(name)
    try:
        result = subprocess.run(
            ["journalctl", "-u", name, f"-n{lines}", "--no-pager", "--output=short"],
            capture_output=True, text=True, timeout=10
        )
        log_lines = result.stdout.splitlines()
    except FileNotFoundError:
        log_lines = ["journalctl not available on this system"]
    return ServiceLog(service=name, lines=log_lines)


def control_service(name: str, action: str) -> dict:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Invalid action: {action!r}. Allowed: {ALLOWED_ACTIONS}")
    _validate_service_name(name)
    try:
        result = subprocess.run(
            ["sudo", "systemctl", action, name],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or f"systemctl {action} failed")
        return {"ok": True, "action": action, "service": name}
    except FileNotFoundError:
        raise RuntimeError("systemctl not found — systemd is not available")


def _validate_service_name(name: str) -> None:
    if not re.match(r'^[a-zA-Z0-9@._\-]+\.service$', name):
        raise ValueError(f"Invalid service name: {name!r}")
