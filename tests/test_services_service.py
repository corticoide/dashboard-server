from unittest.mock import patch
from backend.services.services_service import parse_service_line, list_services, control_service

def test_parse_service_line():
    line = "ssh.service                    loaded active running OpenBSD Secure Shell server"
    svc = parse_service_line(line)
    assert svc["name"] == "ssh.service"
    assert svc["load_state"] == "loaded"
    assert svc["active_state"] == "active"
    assert svc["sub_state"] == "running"
    assert "OpenBSD" in svc["description"]

def test_parse_service_line_inactive():
    line = "cron.service                   loaded inactive dead  Regular background program processing daemon"
    svc = parse_service_line(line)
    assert svc["active_state"] == "inactive"
    assert svc["sub_state"] == "dead"

def test_control_service_invalid_action():
    import pytest
    with pytest.raises(ValueError, match="Invalid action"):
        control_service("ssh.service", "delete")
