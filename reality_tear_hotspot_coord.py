"""pocket-dimension/reality_tear_hotspot_coord.py

Builds hotspot candidates from earth_coverage_field.json,
then saves:
- hotspot index: top hotspots within positive heat bounds and optional lat/lon range
- active endpoints: hotspot->endpoint mapping configs (geometry spawn + simulated endpoint)

This is intentionally data/config oriented (no hard dependency on bridge execution),
so it can be used to drive magi-zone command wiring.
"""

from __future__ import annotations

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


@dataclass
class Hotspot:
    lat_deg: float
    lon_deg: float
    heat: float
    grid_r: Optional[int] = None
    grid_c: Optional[int] = None


def _in_range(x: float, r: Tuple[float, float]) -> bool:
    lo, hi = r
    return lo <= x <= hi


def detect_hotspots_from_field(
    *,
    field: Dict[str, Any],
    lat_range_deg: Tuple[float, float] = (-90.0, 90.0),
    lon_range_deg: Tuple[float, float] = (-180.0, 180.0),
    min_heat: float = 0.25,
    max_hotspots: int = 8,
) -> List[Hotspot]:
    """Detect hotspots by scanning heat_sources and hotspot entry.

    earth_coverage_field.json contains:
    - heat_sources[] with lat_deg/lon_deg/intensity
    - hotspot{lat_deg, lon_deg, heat}

    For robust range filtering we consider both.
    """

    candidates: List[Hotspot] = []

    # Use heat_sources first (they are pre-mapped).
    for hs in (field.get("heat_sources") or []):
        try:
            lat = float(hs.get("lat_deg"))
            lon = float(hs.get("lon_deg"))
            heat = float(hs.get("intensity") if hs.get("intensity") is not None else hs.get("heat", 0.0))
        except Exception:
            continue
        if heat < float(min_heat):
            continue
        if not _in_range(lat, lat_range_deg):
            continue
        if not _in_range(lon, lon_range_deg):
            continue
        candidates.append(Hotspot(lat_deg=lat, lon_deg=lon, heat=heat))

    # Also add the computed max hotspot.
    hp = field.get("hotspot") or {}
    try:
        lat = float(hp.get("lat_deg"))
        lon = float(hp.get("lon_deg"))
        heat = float(hp.get("heat"))
        if heat >= float(min_heat) and _in_range(lat, lat_range_deg) and _in_range(lon, lon_range_deg):
            candidates.append(Hotspot(lat_deg=lat, lon_deg=lon, heat=heat))
    except Exception:
        pass

    # Rank by heat descending.
    candidates.sort(key=lambda h: h.heat, reverse=True)

    # De-duplicate near-identical lat/lon by rounding.
    unique: List[Hotspot] = []
    seen = set()
    for h in candidates:
        key = (round(h.lat_deg, 2), round(h.lon_deg, 2))
        if key in seen:
            continue
        seen.add(key)
        unique.append(h)
        if len(unique) >= max_hotspots:
            break

    return unique


def build_active_endpoints(
    *,
    hotspots: List[Hotspot],
    geometry_type: str = "reality_tear_hydraulic_fringe",
    geometry_min_spawn_heat: float = 0.35,
) -> Dict[str, Any]:
    endpoints: List[Dict[str, Any]] = []

    for idx, h in enumerate(hotspots):
        if h.heat < geometry_min_spawn_heat:
            continue
        endpoints.append(
            {
                "hotspotIndex": idx,
                "hotspot": {
                    "lat_deg": h.lat_deg,
                    "lon_deg": h.lon_deg,
                    "heat": h.heat,
                },
                "geometry": {
                    "type": geometry_type,
                    "center": [h.lat_deg, h.lon_deg, 0.0],
                    "spawnTier": 3,
                    "hotspotRadiusDeg": 10.0,
                    "notes": "placeholder geometry payload; magi-zone wiring will map this into accessibleGeometry",
                },
                "connectedEndpoints": [
                    {
                        "endpointId": f"geom_spawn_{idx}",
                        "kind": "geometry_spawn",
                        "enabled": True,
                    }
                ],
                "timestamp": time.time(),
            }
        )

    return {
        "type": "active_endpoints",
        "generated_at": time.time(),
        "endpoint_count": len(endpoints),
        "endpoints": endpoints,
    }


def main() -> int:
    cfg_path = REPO_ROOT / "pocket-dimension" / "chronos_reality_tears_config.json"
    cfg = _read_json(cfg_path, default={}) or {}

    earth_field_path = REPO_ROOT / cfg.get("input", {}).get("sourceEarthFieldJson", "probe-sequence/spectrum_data/earth_coverage_field.json")
    field = _read_json(earth_field_path, default={}) or {}

    hs_cfg = cfg.get("hotspotDetection", {})
    hotspots = detect_hotspots_from_field(
        field=field,
        lat_range_deg=tuple(hs_cfg.get("latRangeDeg", [-90, 90])) if isinstance(hs_cfg.get("latRangeDeg"), list) else (-90.0, 90.0),
        lon_range_deg=tuple(hs_cfg.get("lonRangeDeg", [-180, 180])) if isinstance(hs_cfg.get("lonRangeDeg"), list) else (-180.0, 180.0),
        min_heat=float(hs_cfg.get("minHeat", 0.25)),
        max_hotspots=int(hs_cfg.get("maxHotspots", 8)),
    )

    hotspot_index = {
        "type": "hotspot_index",
        "source": str(earth_field_path),
        "generated_at": time.time(),
        "hotspots": [
            {"lat_deg": h.lat_deg, "lon_deg": h.lon_deg, "heat": h.heat} for h in hotspots
        ],
    }

    endpoints = build_active_endpoints(
        hotspots=hotspots,
        geometry_type=cfg.get("geometrySpawn", {}).get("geometryType", "reality_tear_hydraulic_fringe"),
        geometry_min_spawn_heat=float(cfg.get("geometrySpawn", {}).get("minSpawnHeat", 0.35)),
    )

    out_hotspot = REPO_ROOT / cfg.get("output", {}).get("hotspotIndexJson", "pocket-dimension/hotspot_index.json")
    out_endpoints = REPO_ROOT / cfg.get("output", {}).get("activeEndpointsJson", "pocket-dimension/active_endpoints.json")
    out_snapshot = REPO_ROOT / cfg.get("output", {}).get("configsSnapshotJson", "pocket-dimension/chronos_reality_tears_snapshot.json")

    _save_json(out_hotspot, hotspot_index)
    _save_json(out_endpoints, endpoints)

    # Save snapshot containing hotspot+config association.
    snapshot = {
        "config": cfg,
        "hotspot_index": hotspot_index,
        "active_endpoints": endpoints,
    }
    _save_json(out_snapshot, snapshot)

    print(json.dumps({"hotspots": len(hotspots), "endpoint_count": endpoints.get("endpoint_count", 0)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

