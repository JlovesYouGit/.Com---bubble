"""hostpoint_resolver.py

Resolution-check / hostpoint resolver:
- Correlates pocket-dimension hotspots -> hostpoints
- Assigns deterministic IP ranges per hostpoint
- Generates mirror DNS hostnames (under a configurable .com mirror root)
- Creates a hostpoints_active.json session object that a client can fetch

Inputs (if present):
- pocket-dimension/hotspot_index.json
- pocket-dimension/active_endpoints.json

Outputs:
- pocket-dimension/hostpoints_active.json
- pocket-dimension/hostpoints_session.json

This repository currently does not include the real-world algorithm you
refer to as "valid .com mirrors under its network". To keep the pipeline
functional end-to-end, this script uses a deterministic placeholder scheme
and centralizes it in functions so you can swap in your true mirror algorithm.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _ip_octets_for_index(hostpoint_index: int) -> Tuple[int, int, int]:
    """Deterministic placeholder: 10.<a>.<b>.0/24.

    You can replace this with the true "entire earth range transmission channels"
    mapping later. Keep it stable so clients can cache.
    """
    a = (hostpoint_index // 256) % 256
    b = hostpoint_index % 256
    return (10, a, b)


def _dns_name_for_hostpoint(hostpoint_id: str, mirror_root: str) -> str:
    """Generate mirror DNS hostname.

    Your requirement: not a schema like example.com; it generates its own
    valid .com mirrors under its network.

    Repo-level placeholder:
      hostpoint-<id>.<mirror_root>

    If you later provide the exact mirror-root algorithm, only this function
    needs to change.
    """
    mirror_root = mirror_root.strip().lstrip(".")
    return f"hostpoint-{hostpoint_id}.{mirror_root}"


@dataclass
class Hostpoint:
    hostpointId: str
    hotspotIndex: int
    geomSpawnEndpointId: Optional[str]
    lat_deg: float
    lon_deg: float
    heat: float
    ipRange: str
    dnsName: str
    transferHostpoint: Optional[str]
    sessionState: str  # "active" or "static"


def build_hostpoints(
    *,
    active_endpoints: Dict[str, Any],
    hotspot_index: Dict[str, Any],
    mirror_root: str,
    session_default_state: str = "active",
) -> List[Hostpoint]:
    endpoints = active_endpoints.get("endpoints") or []

    # Prefer active_endpoints as it already correlates hotspotIndex -> geom_spawn_*
    # If it's missing, fall back to hotspot_index.
    hotspots_from_index: List[Dict[str, Any]] = hotspot_index.get("hotspots") or []

    hostpoints: List[Hostpoint] = []

    for ep in endpoints:
        hotspot_index = int(ep.get("hotspotIndex"))
        hs = ep.get("hotspot") or {}
        lat = float(hs.get("lat_deg", 0.0))
        lon = float(hs.get("lon_deg", 0.0))
        heat = float(hs.get("heat", 0.0))

        connected = (ep.get("connectedEndpoints") or [])
        geom_spawn_id = None
        for c in connected:
            if c.get("kind") == "geometry_spawn":
                geom_spawn_id = c.get("endpointId")
                break

        # hostpointId correlates to the hotspotIndex deterministically.
        hostpoint_id = f"hp_{hotspot_index}"

        oct1, oct2, oct3 = _ip_octets_for_index(hotspot_index)
        ip_range = f"{oct1}.{oct2}.{oct3}.0/24"

        dns_name = _dns_name_for_hostpoint(hostpoint_id, mirror_root)

        # transferHostpoint correlates to geometry id for now.
        transfer_hostpoint = geom_spawn_id

        hostpoints.append(
            Hostpoint(
                hostpointId=hostpoint_id,
                hotspotIndex=hotspot_index,
                geomSpawnEndpointId=geom_spawn_id,
                lat_deg=lat,
                lon_deg=lon,
                heat=heat,
                ipRange=ip_range,
                dnsName=dns_name,
                transferHostpoint=transfer_hostpoint,
                sessionState=session_default_state,
            )
        )

    # If active_endpoints has no entries, fall back to hotspot_index.
    if not hostpoints and hotspots_from_index:
        for hidx, hs in enumerate(hotspots_from_index):
            lat = float(hs.get("lat_deg", 0.0))
            lon = float(hs.get("lon_deg", 0.0))
            heat = float(hs.get("heat", 0.0))
            hostpoint_id = f"hp_{hidx}"
            oct1, oct2, oct3 = _ip_octets_for_index(hidx)
            ip_range = f"{oct1}.{oct2}.{oct3}.0/24"
            dns_name = _dns_name_for_hostpoint(hostpoint_id, mirror_root)
            hostpoints.append(
                Hostpoint(
                    hostpointId=hostpoint_id,
                    hotspotIndex=hidx,
                    geomSpawnEndpointId=None,
                    lat_deg=lat,
                    lon_deg=lon,
                    heat=heat,
                    ipRange=ip_range,
                    dnsName=dns_name,
                    transferHostpoint=None,
                    sessionState=session_default_state,
                )
            )

    # Stable ordering by hotspotIndex
    hostpoints.sort(key=lambda hp: hp.hotspotIndex)
    return hostpoints


def main() -> int:
    parser = argparse.ArgumentParser(description="Resolve pocket-dimension hotspots to hostpoints + IP/DNS + session state")
    parser.add_argument("--mirror-root", type=str, default="mirror.com", help="Root used for generated DNS mirror hostnames")
    parser.add_argument("--session-default", type=str, default="active", choices=["active", "static"], help="Default sessionState")

    args = parser.parse_args()

    active_endpoints_path = REPO_ROOT / "pocket-dimension" / "active_endpoints.json"
    hotspot_index_path = REPO_ROOT / "pocket-dimension" / "hotspot_index.json"

    active_endpoints = _read_json(active_endpoints_path, default={}) or {}
    hotspot_index = _read_json(hotspot_index_path, default={}) or {}

    hostpoints = build_hostpoints(
        active_endpoints=active_endpoints,
        hotspot_index=hotspot_index,
        mirror_root=args.mirror_root,
        session_default_state=args.session_default,
    )

    now = time.time()

    hostpoints_active = {
        "type": "hostpoints_active",
        "generated_at": now,
        "hostpoint_count": len(hostpoints),
        "mirrorRoot": args.mirror_root,
        "hostpoints": [
            {
                "hostpointId": hp.hostpointId,
                "hotspotIndex": hp.hotspotIndex,
                "geomSpawnEndpointId": hp.geomSpawnEndpointId,
                "lat_deg": hp.lat_deg,
                "lon_deg": hp.lon_deg,
                "heat": hp.heat,
                "ipRange": hp.ipRange,
                "dnsName": hp.dnsName,
                "transferHostpoint": hp.transferHostpoint,
                "sessionState": hp.sessionState,
            }
            for hp in hostpoints
        ],
    }

    out_active = REPO_ROOT / "pocket-dimension" / "hostpoints_active.json"
    _save_json(out_active, hostpoints_active)

    # Session snapshot: mutable state for activation flipping.
    hostpoints_session = {
        "type": "hostpoints_session",
        "generated_at": now,
        "hostpoints": {
            hp.hostpointId: {
                "sessionState": hp.sessionState,
                "ipRange": hp.ipRange,
                "dnsName": hp.dnsName,
                "transferHostpoint": hp.transferHostpoint,
                "hotspotIndex": hp.hotspotIndex,
            }
            for hp in hostpoints
        },
    }

    out_session = REPO_ROOT / "pocket-dimension" / "hostpoints_session.json"
    _save_json(out_session, hostpoints_session)

    print(json.dumps({"hostpoint_count": len(hostpoints), "output": str(out_active)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

