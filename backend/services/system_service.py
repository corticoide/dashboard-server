import psutil
import platform
import time as _time
from time import time
from datetime import timezone, datetime as _dt
from backend.schemas.system import SystemMetrics


def _get_utc_info() -> dict:
    """Detect system UTC offset. Respects DST automatically."""
    now = _dt.now(timezone.utc).astimezone()
    offset_seconds = int(now.utcoffset().total_seconds())
    hours = offset_seconds // 3600
    minutes = abs(offset_seconds % 3600) // 60
    sign = '+' if offset_seconds >= 0 else '-'
    if minutes:
        label = f"UTC{sign}{abs(hours):02d}:{minutes:02d}"
    else:
        label = f"UTC{sign}{abs(hours)}"
    # timezone_name from time module (e.g. "ART", "EST")
    tz_name = _time.tzname[0] if _time.tzname else ""
    return {
        "utc_offset_seconds": offset_seconds,
        "utc_label": label,
        "timezone_name": tz_name,
    }


def get_metrics() -> SystemMetrics:
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime = int(time() - psutil.boot_time())
    load = [round(x, 2) for x in psutil.getloadavg()]

    utc = _get_utc_info()
    return SystemMetrics(
        cpu_percent=psutil.cpu_percent(interval=0.1),
        ram_percent=ram.percent,
        ram_used_gb=round(ram.used / 1e9, 2),
        ram_total_gb=round(ram.total / 1e9, 2),
        disk_percent=disk.percent,
        disk_used_gb=round(disk.used / 1e9, 2),
        disk_total_gb=round(disk.total / 1e9, 2),
        uptime_seconds=uptime,
        load_average=load,
        os_name=f"{platform.system()} {platform.release()}",
        hostname=platform.node(),
        cpu_count=psutil.cpu_count(logical=True),
        cpu_arch=platform.machine(),
        utc_offset_seconds=utc["utc_offset_seconds"],
        utc_label=utc["utc_label"],
        timezone_name=utc["timezone_name"],
    )
