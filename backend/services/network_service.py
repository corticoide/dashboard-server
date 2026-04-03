import psutil
from typing import Optional


def get_interfaces() -> list[dict]:
    """Return network interfaces with current cumulative stats."""
    counters = psutil.net_io_counters(pernic=True)
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    result = []
    for name, io in counters.items():
        if name == "lo":
            continue
        ip = mac = ""
        speed = is_up = None
        if name in addrs:
            for addr in addrs[name]:
                if addr.family.name == "AF_INET":
                    ip = addr.address
                elif addr.family.name == "AF_PACKET":
                    mac = addr.address
        if name in stats:
            s = stats[name]
            speed = s.speed  # Mbps, 0 if unknown
            is_up = s.isup
        result.append({
            "name": name,
            "ip": ip,
            "mac": mac,
            "is_up": is_up,
            "speed_mbps": speed,
            "bytes_sent": io.bytes_sent,
            "bytes_recv": io.bytes_recv,
            "packets_sent": io.packets_sent,
            "packets_recv": io.packets_recv,
            "errin": io.errin,
            "errout": io.errout,
            "dropin": io.dropin,
            "dropout": io.dropout,
        })
    return result


def get_active_connections() -> list[dict]:
    """Return active TCP/UDP connections with process info."""
    connections = []
    try:
        for conn in psutil.net_connections(kind="inet"):
            local = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else ""
            remote = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else ""
            proto = "TCP" if conn.type.name == "SOCK_STREAM" else "UDP"
            connections.append({
                "proto": proto,
                "local_addr": local,
                "remote_addr": remote,
                "status": conn.status if conn.status else "NONE",
                "pid": conn.pid,
            })
    except (psutil.AccessDenied, PermissionError):
        # Some connections may not be accessible without root
        pass
    return connections


def get_connection_summary() -> dict:
    """Aggregate connection counts by state for enterprise dashboards."""
    counts: dict[str, int] = {}
    try:
        for conn in psutil.net_connections(kind="inet"):
            state = conn.status if conn.status else "NONE"
            counts[state] = counts.get(state, 0) + 1
    except (psutil.AccessDenied, PermissionError):
        pass
    return counts


def compute_bandwidth_deltas(prev: dict[str, dict], curr: list[dict]) -> list[dict]:
    """
    Compute per-second bandwidth (bytes/s) between two snapshots.
    prev: {iface_name: {bytes_sent, bytes_recv, ts}}
    curr: list of interface dicts from get_interfaces()
    Returns list of {name, sent_bps, recv_bps}
    """
    result = []
    for iface in curr:
        name = iface["name"]
        if name not in prev:
            continue
        p = prev[name]
        elapsed = iface.get("_ts", 0) - p.get("ts", 0)
        if elapsed <= 0:
            continue
        sent_bps = max(0, (iface["bytes_sent"] - p["bytes_sent"]) / elapsed)
        recv_bps = max(0, (iface["bytes_recv"] - p["bytes_recv"]) / elapsed)
        result.append({"name": name, "sent_bps": sent_bps, "recv_bps": recv_bps})
    return result
