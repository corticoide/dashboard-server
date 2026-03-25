from unittest.mock import patch, MagicMock
from backend.services.system_service import get_metrics


def test_get_metrics_returns_expected_fields():
    with patch("backend.services.system_service.psutil") as mock_psutil, \
         patch("backend.services.system_service.time") as mock_time, \
         patch("backend.services.system_service.platform") as mock_platform:

        mock_psutil.cpu_percent.return_value = 42.5
        mock_psutil.virtual_memory.return_value = MagicMock(
            total=8_000_000_000, used=5_000_000_000, percent=62.5
        )
        mock_psutil.disk_usage.return_value = MagicMock(
            total=100_000_000_000, used=40_000_000_000, percent=40.0
        )
        mock_psutil.boot_time.return_value = 1000.0
        mock_psutil.getloadavg.return_value = (1.5, 1.2, 0.9)
        mock_time.return_value = 4600.0
        mock_platform.system.return_value = "Linux"
        mock_platform.release.return_value = "6.6.87"
        mock_platform.node.return_value = "test-host"
        mock_platform.machine.return_value = "x86_64"
        mock_psutil.cpu_count.return_value = 4

        metrics = get_metrics()

    assert metrics.cpu_percent == 42.5
    assert metrics.ram_percent == 62.5
    assert metrics.disk_percent == 40.0
    assert metrics.uptime_seconds == 3600
    assert metrics.load_average == [1.5, 1.2, 0.9]
    assert metrics.os_name == "Linux 6.6.87"
    assert metrics.ram_total_gb > 0
    assert metrics.disk_total_gb > 0
