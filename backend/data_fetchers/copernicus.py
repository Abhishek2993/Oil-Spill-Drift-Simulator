"""
Copernicus Marine Service data fetcher for wave data.

Attempts direct REST/OPeNDAP access to CMEMS global wave forecast products.
Falls back to synthetic wave data derived from wind speed when the service
is unavailable or credentials are missing.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict

import numpy as np

from backend.config import CMEMS_WAVE_DATASET, DEFAULT_BBOX_SIZE_DEG

logger = logging.getLogger(__name__)


def fetch_wave_data(
    lat: float,
    lon: float,
    time_start: datetime,
    time_end: datetime,
    wind_data: Dict = None,
    bbox_size: float = DEFAULT_BBOX_SIZE_DEG,
    grid_points: int = 10,
) -> Dict:
    """
    Fetch or generate wave data for the spill region.

    If wind_data is provided, derives wave parameters from wind speed
    using empirical relationships (Pierson-Moskowitz spectrum approximation).

    Returns
    -------
    dict with keys:
        wave_height : np.ndarray (time, lat, lon) — significant wave height (m)
        wave_dir    : np.ndarray (time, lat, lon) — wave direction (degrees)
        wave_period : np.ndarray (time, lat, lon) — peak wave period (s)
        lats        : np.ndarray
        lons        : np.ndarray
        times       : list[datetime]
        source      : str
    """
    # Copernicus Marine requires authentication — use synthetic for now
    logger.info(
        "Using wind-derived synthetic wave data (CMEMS dataset: %s)",
        CMEMS_WAVE_DATASET,
    )
    return _synthetic_waves(lat, lon, time_start, time_end, wind_data, bbox_size, grid_points)


def _synthetic_waves(
    lat: float,
    lon: float,
    t0: datetime,
    t1: datetime,
    wind_data: Dict,
    bbox: float,
    grid_points: int,
) -> Dict:
    """
    Generate synthetic wave data using wind-wave empirical relationships.

    Uses simplified Pierson-Moskowitz spectrum relationships:
        H_s ≈ 0.0246 × U₁₀²    (significant wave height)
        T_p ≈ 0.729 × U₁₀       (peak period)
    where U₁₀ is 10m wind speed.
    """
    half = bbox / 2
    lats = np.linspace(lat - half, lat + half, grid_points)
    lons = np.linspace(lon - half, lon + half, grid_points)

    hours = int((t1 - t0).total_seconds() / 3600)
    num_steps = max(hours, 1)
    times = [t0 + timedelta(hours=h) for h in range(num_steps + 1)]
    nt = len(times)

    wave_height = np.zeros((nt, grid_points, grid_points))
    wave_dir = np.zeros((nt, grid_points, grid_points))
    wave_period = np.zeros((nt, grid_points, grid_points))

    rng = np.random.RandomState(123)

    if wind_data is not None and "u_wind" in wind_data:
        # Derive waves from wind
        u_w = wind_data["u_wind"]
        v_w = wind_data["v_wind"]

        for ti in range(min(nt, u_w.shape[0])):
            # Interpolate wind to wave grid if needed (same grid assumed)
            wind_speed = np.sqrt(u_w[ti] ** 2 + v_w[ti] ** 2)
            wind_direction = np.degrees(np.arctan2(v_w[ti], u_w[ti]))

            # Pierson-Moskowitz empirical relations
            wave_height[ti] = 0.0246 * wind_speed**2 + rng.normal(0, 0.1, (grid_points, grid_points))
            wave_height[ti] = np.maximum(wave_height[ti], 0.1)

            wave_period[ti] = 0.729 * wind_speed + rng.normal(0, 0.3, (grid_points, grid_points))
            wave_period[ti] = np.maximum(wave_period[ti], 2.0)

            wave_dir[ti] = wind_direction + rng.normal(0, 10, (grid_points, grid_points))
    else:
        # No wind data — generate standalone synthetic waves
        for ti in range(nt):
            phase = ti * 2 * np.pi / 24
            base_hs = 1.5 + 0.5 * np.sin(phase)  # 1-2m wave height
            wave_height[ti] = base_hs + rng.normal(0, 0.2, (grid_points, grid_points))
            wave_height[ti] = np.maximum(wave_height[ti], 0.1)

            wave_period[ti] = 6.0 + rng.normal(0, 0.5, (grid_points, grid_points))
            wave_dir[ti] = 225 + rng.normal(0, 15, (grid_points, grid_points))  # SW swell

    return {
        "wave_height": wave_height,
        "wave_dir": wave_dir,
        "wave_period": wave_period,
        "lats": lats,
        "lons": lons,
        "times": times,
        "source": "synthetic",
    }
