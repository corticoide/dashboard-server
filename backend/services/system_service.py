import psutil
import platform
from time import time
from backend.schemas.system import SystemMetrics


def get_metrics() -> SystemMetrics:
    ram = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    uptime = int(time() - psutil.boot_time())
    load = [round(x, 2) for x in psutil.getloadavg()]

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
    )
