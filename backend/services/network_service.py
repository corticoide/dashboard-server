import psutil
import os
from typing import Optional


def _get_internet_ifaces() -> set:
    """Return set of interface names that have a default route (internet access)."""
    ifaces = set()
    try:
        with open("/proc/net/route") as f:
            next(f)  # skip header
            for line in f:
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "00000000" and parts[2] != "00000000":
                    ifaces.add(parts[0])
    except (OSError, IOError):
        pass
    return ifaces


def _get_subnet(iface_name: str, addrs: dict) -> str:
    """Return subnet in CIDR notation e.g. '192.168.1.0/24'. Empty string on failure."""
    import ipaddress
    if iface_name not in addrs:
        return ""
    for addr in addrs[iface_name]:
        if addr.family.name == "AF_INET" and addr.address and addr.netmask:
            try:
                net = ipaddress.IPv4Network(f"{addr.address}/{addr.netmask}", strict=False)
                return str(net)
            except ValueError:
                pass
    return ""


def get_interfaces() -> list[dict]:
    """Return network interfaces with current cumulative stats."""
    counters = psutil.net_io_counters(pernic=True)
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    internet_ifaces = _get_internet_ifaces()

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
            "is_internet_gateway": name in internet_ifaces,
            "subnet": _get_subnet(name, addrs),
        })
    return result


def _read_connections_proc() -> list[dict]:
    """
    Read TCP/UDP connections from /proc/net/tcp*, /proc/net/udp* — works without root.
    Falls back to empty list on error.
    """
    STATE_MAP = {
        "01": "ESTABLISHED", "02": "SYN_SENT", "03": "SYN_RECV",
        "04": "FIN_WAIT1",   "05": "FIN_WAIT2", "06": "TIME_WAIT",
        "07": "CLOSED",      "08": "CLOSE_WAIT", "09": "LAST_ACK",
        "0A": "LISTEN",      "0B": "CLOSING",
    }

    def hex_to_ip_port(hex_addr: str):
        ip_hex, port_hex = hex_addr.split(":")
        n = int(ip_hex, 16)
        ip = ".".join(str((n >> (8 * i)) & 0xFF) for i in range(4))
        port = int(port_hex, 16)
        return f"{ip}:{port}"

    results = []
    for fname, proto in [("/proc/net/tcp", "TCP"), ("/proc/net/tcp6", "TCP"),
                          ("/proc/net/udp", "UDP"), ("/proc/net/udp6", "UDP")]:
        try:
            with open(fname) as f:
                next(f)  # skip header
                for line in f:
                    parts = line.split()
                    if len(parts) < 4:
                        continue
                    local_hex, remote_hex, state_hex = parts[1], parts[2], parts[3]
                    state = STATE_MAP.get(state_hex.upper(), "NONE")
                    try:
                        local = hex_to_ip_port(local_hex)
                        remote = hex_to_ip_port(remote_hex)
                    except (ValueError, IndexError):
                        continue
                    results.append({
                        "proto": proto,
                        "local_addr": local,
                        "remote_addr": remote if remote != "0.0.0.0:0" else "",
                        "status": state,
                        "pid": None,
                    })
        except (OSError, IOError):
            continue
    return results


def get_active_connections() -> list[dict]:
    """Return active TCP/UDP connections. Tries psutil first, falls back to /proc/net."""
    try:
        connections = []
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
        return connections
    except (psutil.AccessDenied, PermissionError):
        return _read_connections_proc()


def get_connection_summary() -> dict:
    """Aggregate connection counts by state."""
    counts: dict[str, int] = {}
    for conn in get_active_connections():
        state = conn["status"]
        counts[state] = counts.get(state, 0) + 1
    return counts


def get_arp_devices() -> list[dict]:
    """Read ARP table from /proc/net/arp to find LAN devices."""
    devices = []
    try:
        with open("/proc/net/arp") as f:
            next(f)  # skip header
            for line in f:
                parts = line.split()
                if len(parts) < 6:
                    continue
                ip, _, flags, mac, _, iface = parts[:6]
                # flags 0x0 means incomplete/invalid
                if flags == "0x0" or mac == "00:00:00:00:00:00":
                    continue
                devices.append({"ip": ip, "mac": mac, "interface": iface})
    except (OSError, IOError):
        pass
    return devices


def get_network_config() -> dict:
    """Return DNS servers (from /etc/resolv.conf) and default gateway (from /proc/net/route)."""
    dns_servers = []
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2:
                        dns_servers.append(parts[1])
    except (OSError, IOError):
        pass

    gateways = []
    try:
        with open("/proc/net/route") as f:
            next(f)  # skip header
            for line in f:
                parts = line.split()
                if len(parts) < 4:
                    continue
                iface, dest, gw_hex, flags = parts[0], parts[1], parts[2], parts[3]
                # Default route: destination == 00000000 and gateway flag set (0x0003 or 0x0002)
                if dest == "00000000" and gw_hex != "00000000":
                    # Parse little-endian hex IP
                    n = int(gw_hex, 16)
                    ip = ".".join(str((n >> (8 * i)) & 0xFF) for i in range(4))
                    gateways.append({"interface": iface, "gateway": ip})
    except (OSError, IOError):
        pass

    return {"dns_servers": dns_servers, "gateways": gateways}


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
