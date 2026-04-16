from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import get_db
from backend.dependencies import require_permission
from backend.models.network_snapshot import NetworkSnapshot
from backend.schemas.network import InterfaceInfo, ConnectionInfo, ConnectionSummary, BandwidthPoint
from backend.services.network_service import (
    get_interfaces, get_active_connections, get_connection_summary,
    get_arp_devices, get_network_config,
)
from backend.services.cache import TTLCache

router = APIRouter(prefix="/api/network", tags=["network"])

_iface_cache: TTLCache = TTLCache()
_conn_summary_cache: TTLCache = TTLCache()
_IFACE_TTL = 3.0
_SUMMARY_TTL = 5.0


@router.get("/interfaces", response_model=List[InterfaceInfo])
def list_interfaces(user=Depends(require_permission("network", "read"))):
    cached = _iface_cache.get("ifaces")
    if cached is not None:
        return cached
    result = get_interfaces()
    _iface_cache.set("ifaces", result, ttl=_IFACE_TTL)
    return result


@router.get("/connections", response_model=List[ConnectionInfo])
def list_connections(
    status_filter: Optional[str] = Query(None, description="Filter by connection status e.g. ESTABLISHED"),
    proto_filter: Optional[str] = Query(None, description="TCP or UDP"),
    user=Depends(require_permission("network", "read")),
):
    conns = get_active_connections()
    if status_filter:
        conns = [c for c in conns if c["status"] == status_filter.upper()]
    if proto_filter:
        conns = [c for c in conns if c["proto"] == proto_filter.upper()]
    return conns


@router.get("/connections/summary", response_model=ConnectionSummary)
def connections_summary(user=Depends(require_permission("network", "read"))):
    cached = _conn_summary_cache.get("summary")
    if cached is not None:
        return ConnectionSummary(counts=cached)
    counts = get_connection_summary()
    _conn_summary_cache.set("summary", counts, ttl=_SUMMARY_TTL)
    return ConnectionSummary(counts=counts)


@router.get("/bandwidth", response_model=List[BandwidthPoint])
def bandwidth_history(
    interface: Optional[str] = Query(None, description="Filter by interface name"),
    hours: int = Query(24, ge=1, le=720, description="Hours of history (1–720)"),
    db: Session = Depends(get_db),
    user=Depends(require_permission("network", "read")),
):
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    q = db.query(NetworkSnapshot).filter(NetworkSnapshot.timestamp >= cutoff)
    if interface:
        q = q.filter(NetworkSnapshot.interface == interface)
    q = q.order_by(NetworkSnapshot.timestamp.asc())
    rows = q.all()

    if len(rows) > 1440:
        step = len(rows) // 1440
        rows = rows[::step]

    return [
        BandwidthPoint(
            timestamp=r.timestamp,
            interface=r.interface,
            bytes_sent=r.bytes_sent,
            bytes_recv=r.bytes_recv,
        )
        for r in rows
    ]


@router.get("/interfaces/names")
def interface_names(
    db: Session = Depends(get_db),
    user=Depends(require_permission("network", "read")),
):
    """Return list of distinct interface names seen in snapshots (for filter dropdowns)."""
    rows = db.query(NetworkSnapshot.interface).distinct().all()
    return [r[0] for r in rows]


@router.get("/devices")
def arp_devices(user=Depends(require_permission("network", "read"))):
    """Return LAN devices found in the ARP table (/proc/net/arp)."""
    return get_arp_devices()


@router.get("/config")
def network_config(user=Depends(require_permission("network", "read"))):
    """Return network configuration: DNS servers and default gateways."""
    return get_network_config()
