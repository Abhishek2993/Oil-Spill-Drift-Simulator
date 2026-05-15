"""
Oil spill weathering module — evaporation and spatial analysis.

Handles:
  - Exponential evaporation decay of particle mass
  - Convex hull computation for affected zone boundaries
  - Grid-based particle density for risk heatmap generation
"""

import logging
from typing import Dict, List

import numpy as np
from scipy.spatial import ConvexHull

from backend.config import (
    EVAPORATION_RATE_K,
    EVAPORATION_TEMP_FACTOR,
    EVAPORATION_REF_TEMP,
    MIN_MASS_FRACTION,
)

logger = logging.getLogger(__name__)


def apply_evaporation(
    particles,  # ParticleSet (avoid circular import)
    dt: float,
    temperature: float = 20.0,
) -> None:
    """
    Apply exponential evaporation decay to active particles.

    mass(t+dt) = mass(t) × exp(-k_eff × dt)

    where k_eff = k_base × (1 + α × (T - T_ref))

    Particles whose mass drops below MIN_MASS_FRACTION are deactivated.
    """
    active = particles.active
    if not active.any():
        return

    # Temperature-adjusted evaporation rate
    k_eff = EVAPORATION_RATE_K * (
        1 + EVAPORATION_TEMP_FACTOR * (temperature - EVAPORATION_REF_TEMP)
    )

    # Apply exponential decay
    decay_factor = np.exp(-k_eff * dt)
    particles.mass[active] *= decay_factor

    # Deactivate particles below threshold
    below_threshold = (particles.mass < MIN_MASS_FRACTION) & active
    num_deactivated = below_threshold.sum()
    if num_deactivated > 0:
        particles.active[below_threshold] = False
        logger.debug("Deactivated %d particles (evaporated)", num_deactivated)


def compute_affected_zone(particles) -> Dict:
    """
    Compute the convex hull of active particles as a GeoJSON Polygon.

    Returns a GeoJSON-compatible dict, or an empty polygon if too few
    active particles.
    """
    active = particles.active
    if active.sum() < 3:
        return {"type": "Polygon", "coordinates": []}

    points = np.column_stack([
        particles.lons[active],
        particles.lats[active],
    ])

    try:
        hull = ConvexHull(points)
        hull_points = points[hull.vertices]

        # Close the polygon (first point = last point)
        coords = []
        for p in hull_points:
            coords.append([round(float(p[0]), 6), round(float(p[1]), 6)])
        coords.append(coords[0])  # close ring

        return {
            "type": "Polygon",
            "coordinates": [coords],
        }
    except Exception as exc:
        logger.warning("Convex hull failed: %s", exc)
        return {"type": "Polygon", "coordinates": []}


def compute_particle_density(
    particles,
    grid_resolution: float = 0.01,
    radius_cells: int = 2,
) -> Dict:
    """
    Compute a gridded particle density map for heatmap rendering.

    Returns a dict with:
        bounds : [[lat_min, lon_min], [lat_max, lon_max]]
        grid   : 2D list of density values (normalized 0-1)
        rows   : number of latitude rows
        cols   : number of longitude columns
    """
    active = particles.active
    if active.sum() == 0:
        return {"bounds": [[0, 0], [0, 0]], "grid": [], "rows": 0, "cols": 0}

    lats = particles.lats[active]
    lons = particles.lons[active]
    mass = particles.mass[active]

    # Determine bounds with padding
    pad = grid_resolution * 5
    lat_min, lat_max = float(lats.min()) - pad, float(lats.max()) + pad
    lon_min, lon_max = float(lons.min()) - pad, float(lons.max()) + pad

    # Create grid
    lat_bins = np.arange(lat_min, lat_max + grid_resolution, grid_resolution)
    lon_bins = np.arange(lon_min, lon_max + grid_resolution, grid_resolution)
    nrows = len(lat_bins) - 1
    ncols = len(lon_bins) - 1

    if nrows <= 0 or ncols <= 0:
        return {"bounds": [[lat_min, lon_min], [lat_max, lon_max]], "grid": [], "rows": 0, "cols": 0}

    # Bin particles into grid cells, weighted by mass
    density = np.zeros((nrows, ncols))
    lat_idx = np.digitize(lats, lat_bins) - 1
    lon_idx = np.digitize(lons, lon_bins) - 1

    # Clamp indices
    lat_idx = np.clip(lat_idx, 0, nrows - 1)
    lon_idx = np.clip(lon_idx, 0, ncols - 1)

    for i in range(len(lats)):
        li, lo = lat_idx[i], lon_idx[i]
        # Spread influence to neighboring cells
        for di in range(-radius_cells, radius_cells + 1):
            for dj in range(-radius_cells, radius_cells + 1):
                ni, nj = li + di, lo + dj
                if 0 <= ni < nrows and 0 <= nj < ncols:
                    dist = np.sqrt(di**2 + dj**2)
                    weight = mass[i] * np.exp(-dist**2 / 2)
                    density[ni, nj] += weight

    # Normalize to [0, 1]
    max_val = density.max()
    if max_val > 0:
        density /= max_val

    # Convert to list format for JSON
    grid_list = density.tolist()

    return {
        "bounds": [
            [round(lat_min, 6), round(lon_min, 6)],
            [round(lat_max, 6), round(lon_max, 6)],
        ],
        "grid": grid_list,
        "rows": nrows,
        "cols": ncols,
    }


def compute_spread_area_km2(particles) -> float:
    """
    Estimate the affected area in km² from the convex hull of active particles.
    """
    active = particles.active
    if active.sum() < 3:
        return 0.0

    points = np.column_stack([
        particles.lons[active],
        particles.lats[active],
    ])

    try:
        hull = ConvexHull(points)
        # Hull volume in 2D = area in degrees²
        area_deg2 = hull.volume
        # Convert to km² (approximate)
        avg_lat = float(points[:, 1].mean())
        km_per_deg_lat = 111.32
        km_per_deg_lon = 111.32 * np.cos(np.radians(avg_lat))
        area_km2 = area_deg2 * km_per_deg_lat * km_per_deg_lon
        return round(area_km2, 2)
    except Exception:
        return 0.0
