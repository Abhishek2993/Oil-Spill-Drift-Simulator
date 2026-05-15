"""
NOAA ERDDAP data fetcher for ocean currents (OSCAR) and wind (GFS).

Constructs ERDDAP griddap REST URLs, fetches JSON data, and parses into
NumPy arrays. Falls back to physics-based synthetic data when the API
is unreachable or returns errors.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

import numpy as np
import requests

from backend.config import (
    ERDDAP_OSCAR_BASE,
    ERDDAP_OSCAR_DATASET,
    ERDDAP_GFS_BASE,
    ERDDAP_GFS_DATASET,
    DEFAULT_BBOX_SIZE_DEG,
)

logger = logging.getLogger(__name__)

# Request timeout for ERDDAP calls (seconds)
_TIMEOUT = 15


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def fetch_ocean_currents(
    lat: float,
    lon: float,
    time_start: datetime,
    time_end: datetime,
    bbox_size: float = DEFAULT_BBOX_SIZE_DEG,
    grid_points: int = 10,
) -> Dict:
    """
    Fetch OSCAR ocean surface current data for a bounding box around
    the spill site.

    Returns
    -------
    dict with keys:
        u       : np.ndarray (time, lat, lon) — eastward velocity (m/s)
        v       : np.ndarray (time, lat, lon) — northward velocity (m/s)
        lats    : np.ndarray — latitude grid
        lons    : np.ndarray — longitude grid
        times   : list[datetime] — time steps
        source  : str — 'erddap' or 'synthetic'
    """
    try:
        data = _fetch_erddap_current(lat, lon, time_start, time_end, bbox_size)
        data["source"] = "erddap"
        logger.info("Fetched OSCAR currents from ERDDAP (%d time steps)", len(data["times"]))
        return data
    except Exception as exc:
        logger.warning("ERDDAP current fetch failed (%s), using synthetic data", exc)
        return _synthetic_currents(lat, lon, time_start, time_end, bbox_size, grid_points)


def fetch_wind_data(
    lat: float,
    lon: float,
    time_start: datetime,
    time_end: datetime,
    bbox_size: float = DEFAULT_BBOX_SIZE_DEG,
    grid_points: int = 10,
) -> Dict:
    """
    Fetch GFS 10-meter wind data for a bounding box around the spill site.

    Returns
    -------
    dict with keys:
        u_wind  : np.ndarray (time, lat, lon) — eastward wind (m/s)
        v_wind  : np.ndarray (time, lat, lon) — northward wind (m/s)
        lats    : np.ndarray
        lons    : np.ndarray
        times   : list[datetime]
        source  : str
    """
    try:
        data = _fetch_erddap_wind(lat, lon, time_start, time_end, bbox_size)
        data["source"] = "erddap"
        logger.info("Fetched GFS wind from ERDDAP (%d time steps)", len(data["times"]))
        return data
    except Exception as exc:
        logger.warning("ERDDAP wind fetch failed (%s), using synthetic data", exc)
        return _synthetic_wind(lat, lon, time_start, time_end, bbox_size, grid_points)


# ─────────────────────────────────────────────────────────────────────────────
# ERDDAP helpers
# ─────────────────────────────────────────────────────────────────────────────

def _fmt_time(dt: datetime) -> str:
    """Format datetime for ERDDAP constraint."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _fetch_erddap_current(lat, lon, t0, t1, bbox) -> Dict:
    """Query OSCAR griddap for u/v currents."""
    half = bbox / 2
    lat_lo, lat_hi = lat - half, lat + half
    lon_lo, lon_hi = lon - half, lon + half

    base = f"{ERDDAP_OSCAR_BASE}/{ERDDAP_OSCAR_DATASET}.json"
    query = (
        f"?u[({_fmt_time(t0)}):1:({_fmt_time(t1)})]"
        f"[(0.0)]"
        f"[({lat_lo}):1:({lat_hi})]"
        f"[({lon_lo}):1:({lon_hi})]"
        f",v[({_fmt_time(t0)}):1:({_fmt_time(t1)})]"
        f"[(0.0)]"
        f"[({lat_lo}):1:({lat_hi})]"
        f"[({lon_lo}):1:({lon_hi})]"
    )
    url = base + query
    logger.debug("OSCAR URL: %s", url)

    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    return _parse_erddap_grid(payload, var_names=["u", "v"], vel_keys=["u", "v"])


def _fetch_erddap_wind(lat, lon, t0, t1, bbox) -> Dict:
    """Query GFS griddap for 10m wind components."""
    half = bbox / 2
    lat_lo, lat_hi = lat - half, lat + half
    lon_lo, lon_hi = lon - half, lon + half

    base = f"{ERDDAP_GFS_BASE}/{ERDDAP_GFS_DATASET}.json"
    query = (
        f"?ugrd10m[({_fmt_time(t0)}):1:({_fmt_time(t1)})]"
        f"[({lat_lo}):1:({lat_hi})]"
        f"[({lon_lo}):1:({lon_hi})]"
        f",vgrd10m[({_fmt_time(t0)}):1:({_fmt_time(t1)})]"
        f"[({lat_lo}):1:({lat_hi})]"
        f"[({lon_lo}):1:({lon_hi})]"
    )
    url = base + query
    logger.debug("GFS URL: %s", url)

    resp = requests.get(url, timeout=_TIMEOUT)
    resp.raise_for_status()
    payload = resp.json()

    return _parse_erddap_grid(payload, var_names=["ugrd10m", "vgrd10m"],
                               vel_keys=["u_wind", "v_wind"])


def _parse_erddap_grid(payload: dict, var_names: list, vel_keys: list) -> Dict:
    """
    Parse ERDDAP JSON table response into structured arrays.
    ERDDAP returns { "table": { "columnNames": [...], "rows": [...] } }
    """
    table = payload["table"]
    col_names = table["columnNames"]
    rows = table["rows"]

    # Extract unique coordinate values
    time_idx = col_names.index("time")
    lat_idx = col_names.index("latitude")
    lon_idx = col_names.index("longitude")

    times_raw = sorted(set(r[time_idx] for r in rows))
    lats_raw = sorted(set(r[lat_idx] for r in rows))
    lons_raw = sorted(set(r[lon_idx] for r in rows))

    nt, nlat, nlon = len(times_raw), len(lats_raw), len(lons_raw)

    # Build lookup indices
    t_map = {v: i for i, v in enumerate(times_raw)}
    lat_map = {v: i for i, v in enumerate(lats_raw)}
    lon_map = {v: i for i, v in enumerate(lons_raw)}

    # We expect the first velocity variable columns
    var_indices = [col_names.index(v) for v in var_names]

    arrays = {k: np.full((nt, nlat, nlon), np.nan) for k in vel_keys}

    for row in rows:
        ti = t_map[row[time_idx]]
        li = lat_map[row[lat_idx]]
        lo = lon_map[row[lon_idx]]
        for vi, key in zip(var_indices, vel_keys):
            val = row[vi]
            if val is not None:
                arrays[key][ti, li, lo] = float(val)

    # Replace remaining NaN with 0
    for k in vel_keys:
        np.nan_to_num(arrays[k], copy=False, nan=0.0)

    times = [datetime.fromisoformat(t.replace("Z", "+00:00")) for t in times_raw]

    return {
        **arrays,
        "lats": np.array(lats_raw),
        "lons": np.array(lons_raw),
        "times": times,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic fallback data generators
# ─────────────────────────────────────────────────────────────────────────────

def _synthetic_currents(
    lat: float, lon: float,
    t0: datetime, t1: datetime,
    bbox: float, grid_points: int,
) -> Dict:
    """
    Generate a synthetic ocean current field using a simple gyre pattern.
    Provides realistic-looking flow for demonstration purposes.
    """
    half = bbox / 2
    lats = np.linspace(lat - half, lat + half, grid_points)
    lons = np.linspace(lon - half, lon + half, grid_points)

    hours = int((t1 - t0).total_seconds() / 3600)
    num_steps = max(hours, 1)
    times = [t0 + timedelta(hours=h) for h in range(num_steps + 1)]

    nt = len(times)
    u = np.zeros((nt, grid_points, grid_points))
    v = np.zeros((nt, grid_points, grid_points))

    # Create a mesoscale gyre pattern with slight temporal variation
    lon_grid, lat_grid = np.meshgrid(lons, lats)
    cx, cy = lon, lat

    for ti in range(nt):
        phase = ti * 0.02  # slow rotation
        # Gyre-like flow: circular pattern around center
        dx = (lon_grid - cx) * np.pi / half
        dy = (lat_grid - cy) * np.pi / half
        r = np.sqrt(dx**2 + dy**2) + 1e-10

        speed = 0.3 * np.exp(-r**2 / 2)  # ~0.3 m/s peak
        u[ti] = -speed * np.sin(dy + phase) + 0.05  # slight eastward background
        v[ti] = speed * np.cos(dx + phase) + 0.02   # slight northward background

    logger.info("Generated synthetic current field (%d×%d, %d steps)", grid_points, grid_points, nt)
    return {
        "u": u, "v": v,
        "lats": lats, "lons": lons,
        "times": times,
        "source": "synthetic",
    }


def _synthetic_wind(
    lat: float, lon: float,
    t0: datetime, t1: datetime,
    bbox: float, grid_points: int,
) -> Dict:
    """
    Generate synthetic wind field with realistic variability.
    Models a prevailing wind with turbulent fluctuations.
    """
    half = bbox / 2
    lats = np.linspace(lat - half, lat + half, grid_points)
    lons = np.linspace(lon - half, lon + half, grid_points)

    hours = int((t1 - t0).total_seconds() / 3600)
    num_steps = max(hours, 1)
    times = [t0 + timedelta(hours=h) for h in range(num_steps + 1)]

    nt = len(times)
    rng = np.random.RandomState(42)

    # Prevailing wind: ~5 m/s from the southeast (common Gulf pattern)
    base_u = 4.0   # eastward component
    base_v = -2.0  # southward component

    u_wind = np.zeros((nt, grid_points, grid_points))
    v_wind = np.zeros((nt, grid_points, grid_points))

    for ti in range(nt):
        # Slow sinusoidal variation + random turbulence
        phase = ti * 2 * np.pi / 24  # daily cycle
        u_wind[ti] = base_u + 1.5 * np.sin(phase) + rng.normal(0, 0.5, (grid_points, grid_points))
        v_wind[ti] = base_v + 1.0 * np.cos(phase) + rng.normal(0, 0.5, (grid_points, grid_points))

    logger.info("Generated synthetic wind field (%d×%d, %d steps)", grid_points, grid_points, nt)
    return {
        "u_wind": u_wind, "v_wind": v_wind,
        "lats": lats, "lons": lons,
        "times": times,
        "source": "synthetic",
    }
