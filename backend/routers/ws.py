"""
WebSocket endpoints for real-time server metrics and network stats.
Connections are authenticated via ?token= query param (JWT).
"""
import asyncio
import json
import logging
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from backend.services.auth_service import decode_token
from backend.services.system_service import get_metrics
from backend.services.network_service import get_interfaces

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ws", tags=["websocket"])


def _auth_token(token: str) -> bool:
    """Return True if token is valid, False otherwise."""
    try:
        decode_token(token)
        return True
    except Exception:
        return False


@router.websocket("/metrics")
async def ws_metrics(websocket: WebSocket, token: str = Query("")):
    """
    Push system metrics every second.
    Client connects to: wss://host/api/ws/metrics?token=<jwt>
    """
    if not _auth_token(token):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    logger.info("WS /metrics client connected")
    from fastapi.concurrency import run_in_threadpool
    try:
        while True:
            m = await run_in_threadpool(get_metrics)
            await websocket.send_text(json.dumps({
                "cpu_percent": m.cpu_percent,
                "ram_percent": m.ram_percent,
                "ram_used_gb": m.ram_used_gb,
                "ram_total_gb": m.ram_total_gb,
                "disk_percent": m.disk_percent,
                "disk_used_gb": m.disk_used_gb,
                "disk_total_gb": m.disk_total_gb,
                "uptime_seconds": m.uptime_seconds,
                "load_average": m.load_average,
                "os_name": m.os_name,
                "hostname": m.hostname,
                "cpu_count": m.cpu_count,
                "cpu_arch": m.cpu_arch,
                "utc_offset_seconds": m.utc_offset_seconds,
                "utc_label": m.utc_label,
                "timezone_name": m.timezone_name,
            }))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("WS /metrics client disconnected")
    except Exception as e:
        logger.exception("WS /metrics error: %s", e)


@router.websocket("/network")
async def ws_network(websocket: WebSocket, token: str = Query("")):
    """
    Push live interface stats + per-second bandwidth deltas every 2 seconds.
    Client connects to: wss://host/api/ws/network?token=<jwt>
    Payload: { interfaces: [...], bps: { eth0: { sent_bps, recv_bps } } }
    """
    if not _auth_token(token):
        await websocket.close(code=4001)
        return

    await websocket.accept()
    logger.info("WS /network client connected")

    prev: dict[str, dict] = {}
    import time
    from fastapi.concurrency import run_in_threadpool

    try:
        while True:
            now = time.monotonic()
            ifaces = await run_in_threadpool(get_interfaces)

            bps: dict[str, dict] = {}
            for iface in ifaces:
                name = iface["name"]
                if name in prev:
                    p = prev[name]
                    elapsed = now - p["ts"]
                    if elapsed > 0:
                        bps[name] = {
                            "sent_bps": max(0, (iface["bytes_sent"] - p["bytes_sent"]) / elapsed),
                            "recv_bps": max(0, (iface["bytes_recv"] - p["bytes_recv"]) / elapsed),
                        }
                prev[name] = {
                    "bytes_sent": iface["bytes_sent"],
                    "bytes_recv": iface["bytes_recv"],
                    "ts": now,
                }

            await websocket.send_text(json.dumps({
                "interfaces": ifaces,
                "bps": bps,
            }))
            await asyncio.sleep(2)
    except WebSocketDisconnect:
        logger.info("WS /network client disconnected")
    except Exception as e:
        logger.exception("WS /network error: %s", e)


@router.websocket("/log-tail")
async def ws_log_tail(
    websocket: WebSocket,
    path: str = Query(""),
    token: str = Query(""),
):
    """
    Stream new lines from a /var/log file as they are appended.
    Client: wss://host/api/ws/log-tail?path=/var/log/syslog&token=<jwt>
    """
    if not _auth_token(token):
        await websocket.close(code=4001)
        return

    log_root = Path("/var/log")
    try:
        p = Path(path).resolve()
    except Exception:
        await websocket.close(code=4003)
        return
    if not p.is_relative_to(log_root) or not p.is_file():
        await websocket.close(code=4003)
        return

    try:
        f = open(p, "r", errors="replace")
    except PermissionError:
        await websocket.close(code=4003)
        return

    await websocket.accept()
    logger.info("WS /log-tail connected: %s", path)

    # Seek to end — send only new content
    f.seek(0, 2)

    try:
        while True:
            chunk = f.read()
            if chunk:
                await websocket.send_text(chunk)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        logger.info("WS /log-tail disconnected: %s", path)
    except Exception as e:
        logger.exception("WS /log-tail error: %s", e)
    finally:
        f.close()
