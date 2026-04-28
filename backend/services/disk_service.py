"""Disk management service — lsblk + udisksctl + optional smartctl."""
import json
import subprocess
import time
from typing import Optional
from sqlalchemy.orm import Session

from backend.services.settings_service import get_setting, upsert_setting

# ── IO rate cache — updated by scheduler every 5 s ─────────────────────────
_io_rates: dict[str, tuple[float, float]] = {}
_diskstats_snap: dict[str, tuple[int, int, float]] = {}  # dev → (sr, sw, ts)

# ── SMART cache — updated by scheduler every 5 min ─────────────────────────
_smart_cache: dict[str, dict] = {}

# Theoretical max MB/s by disk type (for read/write percentage bars)
_TYPE_MAX_MB: dict[str, tuple[float, float]] = {
    "NVMe": (7000.0, 5000.0),
    "SSD":  (550.0,  520.0),
    "HDD":  (200.0,  180.0),
    "USB":  (150.0,   60.0),
}


# ── Helpers ─────────────────────────────────────────────────────────────────

def _detect_type(tran: str, rota: str, rm: str) -> str:
    t = tran.lower()
    if t == "nvme":               return "NVMe"
    if t == "usb" or rm == "1":  return "USB"
    if rota == "1":               return "HDD"
    return "SSD"


def _interface_label(tran: str, dtype: str) -> str:
    t = tran.lower()
    if dtype == "NVMe": return f"PCIe NVMe ({t.upper()})"
    if dtype == "USB":  return "USB"
    return "SATA"


def _fmt_bytes(b: int) -> str:
    if b >= 1024 ** 4: return f"{b / 1024 ** 4:.1f} TB"
    if b >= 1024 ** 3: return f"{b / 1024 ** 3:.1f} GB"
    if b >= 1024 ** 2: return f"{b / 1024 ** 2:.0f} MB"
    return f"{b} B"


def _guess_part_type(fstype: str) -> str:
    fs = (fstype or "").lower()
    if fs in ("vfat", "fat32", "fat16", "fat"): return "EFI"
    if fs == "swap":                             return "Swap"
    if fs in ("ntfs", "exfat"):                  return "Windows"
    return "Linux"


def _get_partition_usage(mount: Optional[str]) -> tuple[int, int]:
    if not mount or mount in ("[SWAP]", "—"):
        return (0, 0)
    try:
        import shutil
        u = shutil.disk_usage(mount)
        return (u.used, u.total)
    except OSError:
        return (0, 0)


# ── SMART sampling (scheduler calls this every 5 min) ───────────────────────

def _sample_one_smart(dev_name: str) -> dict:
    result: dict = {}
    try:
        r = subprocess.run(
            ["smartctl", "-j", "-A", "-H", f"/dev/{dev_name}"],
            capture_output=True, text=True, timeout=8,
        )
        data = json.loads(r.stdout or "{}")
        status = data.get("smart_status", {})
        if isinstance(status.get("passed"), bool):
            result["smart"]  = "PASSED" if status["passed"] else "FAILED"
            result["health"] = 97 if status["passed"] else 20
        temp_obj = data.get("temperature", {})
        if isinstance(temp_obj.get("current"), (int, float)):
            result["temp"] = int(temp_obj["current"])
        for attr in data.get("ata_smart_attributes", {}).get("table", []):
            name = attr.get("name", "")
            if name == "Wear_Leveling_Count":
                result["health"] = attr.get("value", result.get("health", 97))
            if name == "Temperature_Celsius":
                result.setdefault("temp", attr.get("raw", {}).get("value"))
        rotation = data.get("rotation_rate")
        if isinstance(rotation, int) and rotation > 0:
            result["rpm"] = rotation
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return result


def sample_smart_all(dev_names: list[str]) -> None:
    """Pure work function called by the scheduler job wrapper."""
    for dev in dev_names:
        data = _sample_one_smart(dev)
        if data:
            _smart_cache[dev] = data


# ── IO sampling (scheduler calls this every 5 s) ────────────────────────────

def _read_diskstats() -> dict[str, tuple[int, int]]:
    out: dict[str, tuple[int, int]] = {}
    try:
        with open("/proc/diskstats") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 10:
                    out[parts[2]] = (int(parts[5]), int(parts[9]))
    except OSError:
        pass
    return out


def sample_disk_io() -> None:
    """Pure work function called by the scheduler job wrapper."""
    global _diskstats_snap, _io_rates
    now = time.monotonic()
    current = _read_diskstats()
    for dev, (sr, sw) in current.items():
        if dev in _diskstats_snap:
            prev_sr, prev_sw, prev_ts = _diskstats_snap[dev]
            dt = now - prev_ts
            if dt > 0:
                read_mb  = max(0.0, (sr - prev_sr) * 512 / dt / (1024 * 1024))
                write_mb = max(0.0, (sw - prev_sw) * 512 / dt / (1024 * 1024))
                _io_rates[dev] = (round(read_mb, 1), round(write_mb, 1))
        _diskstats_snap[dev] = (sr, sw, now)


# ── Public API ───────────────────────────────────────────────────────────────

def list_dev_names() -> list[str]:
    """Fast lsblk to get top-level disk device names."""
    try:
        r = subprocess.run(
            ["lsblk", "-J", "-b", "-o", "NAME,TYPE"],
            capture_output=True, text=True, timeout=5,
        )
        data = json.loads(r.stdout or "{}")
        return [d["name"] for d in data.get("blockdevices", []) if d.get("type") == "disk"]
    except Exception:
        return []


def list_disks(db: Session) -> list[dict]:
    """Return enriched disk list. Runs in threadpool — may block briefly for lsblk."""
    try:
        r = subprocess.run(
            ["lsblk", "-J", "-b", "-o",
             "NAME,TYPE,SIZE,FSTYPE,MOUNTPOINT,UUID,MODEL,SERIAL,TRAN,ROTA,RM"],
            capture_output=True, text=True, timeout=10,
        )
        raw = json.loads(r.stdout or "{}")
    except Exception:
        return []

    result = []
    for dev in raw.get("blockdevices", []):
        if dev.get("type") != "disk":
            continue

        dev_name = dev["name"]
        tran  = (dev.get("tran")  or "").lower()
        rota  = str(dev.get("rota") or "0")
        rm    = str(dev.get("rm")  or "0")
        dtype = _detect_type(tran, rota, rm)

        custom_name = get_setting(db, f"disk_name:{dev_name}",
                                  (dev.get("model") or dev_name).strip())
        favorite = get_setting(db, f"disk_favorite:{dev_name}", "false") == "true"

        size_bytes = int(dev.get("size") or 0)

        # Partitions + aggregate usage
        partitions: list[dict] = []
        total_used = 0
        mount_point: Optional[str] = dev.get("mountpoint")
        status = "unmounted"

        for child in dev.get("children") or []:
            if child.get("type") not in ("part", "lvm"):
                continue
            cfs    = child.get("fstype") or "—"
            cmount = child.get("mountpoint")
            csz    = int(child.get("size") or 0)
            u, _   = _get_partition_usage(cmount)
            total_used += u
            if cmount and cmount not in ("[SWAP]", "—"):
                status = "mounted"
                if not mount_point:
                    mount_point = cmount
            partitions.append({
                "name":  child["name"],
                "size":  _fmt_bytes(csz),
                "fs":    cfs,
                "mount": cmount or "—",
                "type":  _guess_part_type(cfs),
            })

        # Disk itself may be directly mounted (no partition table)
        if dev.get("mountpoint"):
            status = "mounted"
            mount_point = dev["mountpoint"]
            u, _ = _get_partition_usage(mount_point)
            total_used = u

        # Primary FS
        fs = dev.get("fstype") or "—"
        if fs == "—":
            for child in dev.get("children") or []:
                cf = child.get("fstype") or ""
                if cf and cf != "swap":
                    fs = cf
                    break

        # UUID from first partition with one
        uuid = dev.get("uuid") or "—"
        if uuid == "—":
            for child in dev.get("children") or []:
                if child.get("uuid"):
                    uuid = child["uuid"]
                    break

        smart = _smart_cache.get(dev_name, {})
        read_mb, write_mb = _io_rates.get(dev_name, (0.0, 0.0))
        max_r, max_w = _TYPE_MAX_MB.get(dtype, (200.0, 180.0))

        result.append({
            "id":         dev_name,
            "name":       custom_name,
            "dev":        f"/dev/{dev_name}",
            "favorite":   favorite,
            "type":       dtype,
            "model":      (dev.get("model") or "—").strip(),
            "serial":     (dev.get("serial") or "—").strip(),
            "size":       size_bytes,
            "used":       total_used,
            "fs":         fs,
            "mount":      mount_point,
            "uuid":       uuid,
            "temp":       smart.get("temp"),
            "health":     smart.get("health"),
            "smart":      smart.get("smart", "N/A"),
            "read":       read_mb,
            "write":      write_mb,
            "read_pct":   round(min(1.0, read_mb  / max_r)  if max_r  else 0.0, 3),
            "write_pct":  round(min(1.0, write_mb / max_w)  if max_w  else 0.0, 3),
            "rpm":        smart.get("rpm"),
            "status":     status,
            "interface":  _interface_label(tran, dtype),
            "partitions": partitions,
        })

    return result


def set_disk_name(db: Session, disk_id: str, name: str) -> None:
    upsert_setting(db, f"disk_name:{disk_id}", name.strip()[:64])
    db.commit()


def set_disk_favorite(db: Session, disk_id: str, favorite: bool) -> None:
    upsert_setting(db, f"disk_favorite:{disk_id}", "true" if favorite else "false")
    db.commit()


def mount_disk(dev: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["udisksctl", "mount", "-b", dev],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0, (r.stdout or r.stderr).strip()
    except Exception as exc:
        return False, str(exc)


def unmount_disk(dev: str) -> tuple[bool, str]:
    try:
        r = subprocess.run(
            ["udisksctl", "unmount", "-b", dev],
            capture_output=True, text=True, timeout=15,
        )
        return r.returncode == 0, (r.stdout or r.stderr).strip()
    except Exception as exc:
        return False, str(exc)
