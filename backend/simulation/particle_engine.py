"""
Lagrangian Particle Tracking Engine for oil spill simulation.

Implements RK4 (Runge-Kutta 4th order) integration of particle positions
under combined ocean current + wind drift forcing, with random diffusion
and evaporation weathering.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.interpolate import RegularGridInterpolator

from backend.config import (
    DEFAULT_NUM_PARTICLES,
    DEFAULT_TIMESTEP_SECONDS,
    DEFAULT_FORECAST_HOURS,
    DEFAULT_VOLUME_BARRELS,
    WIND_DRIFT_FACTOR,
    WIND_DRIFT_ANGLE_DEG,
    HORIZONTAL_DIFFUSIVITY,
    EARTH_RADIUS_M,
    DEG_TO_M_LAT,
)
from backend.data_fetchers.noaa_erddap import fetch_ocean_currents, fetch_wind_data
from backend.data_fetchers.copernicus import fetch_wave_data
from backend.simulation.weathering import (
    apply_evaporation,
    compute_affected_zone,
    compute_particle_density,
    compute_spread_area_km2
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data structures
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ParticleSet:
    """State of all particles at a single moment."""
    lats: np.ndarray          # (N,) latitude of each particle
    lons: np.ndarray          # (N,) longitude of each particle
    mass: np.ndarray          # (N,) remaining mass fraction [0, 1]
    active: np.ndarray        # (N,) boolean — still contributing to spill
    initial_mass: np.ndarray  # (N,) initial mass for each particle
    num_particles: int = 0

    def __post_init__(self):
        self.num_particles = len(self.lats)


@dataclass
class SimulationResult:
    """Complete simulation output."""
    timesteps: List[Dict]
    heatmap: Dict
    metadata: Dict


# ─────────────────────────────────────────────────────────────────────────────
# Initialization
# ─────────────────────────────────────────────────────────────────────────────

def initialize_particles(
    lat: float,
    lon: float,
    num_particles: int,
    volume_barrels: float,
) -> ParticleSet:
    """
    Scatter particles in a Gaussian cloud around the spill origin.
    Initial spread radius scales with volume (~Fay spreading law).
    """
    rng = np.random.RandomState(42)

    # Initial spread radius (degrees) — scales as V^(1/4) from Fay's law
    # ~0.001 degrees ≈ 100m for a 1000-barrel spill
    radius_deg = 0.001 * (volume_barrels / 1000) ** 0.25

    lats = lat + rng.normal(0, radius_deg, num_particles)
    lons = lon + rng.normal(0, radius_deg / np.cos(np.radians(lat)), num_particles)

    # Mass per particle (equal distribution)
    mass_per = np.ones(num_particles)
    initial = np.ones(num_particles)

    return ParticleSet(
        lats=lats,
        lons=lons,
        mass=mass_per,
        active=np.ones(num_particles, dtype=bool),
        initial_mass=initial,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Interpolation
# ─────────────────────────────────────────────────────────────────────────────

def _build_interpolator(
    field: np.ndarray,
    lats: np.ndarray,
    lons: np.ndarray,
) -> RegularGridInterpolator:
    """Build a 2D spatial interpolator for a single time slice."""
    return RegularGridInterpolator(
        (lats, lons), field,
        method="linear",
        bounds_error=False,
        fill_value=0.0,
    )


def interpolate_velocity(
    current_data: Dict,
    wind_data: Dict,
    time_idx: int,
    particle_lats: np.ndarray,
    particle_lons: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Interpolate current + wind-drift velocity to particle positions.

    Effective velocity = ocean_current + WIND_DRIFT_FACTOR × wind
    with a clockwise deflection of WIND_DRIFT_ANGLE_DEG.

    Returns (u_eff, v_eff) in m/s.
    """
    n = len(particle_lats)
    ti = min(time_idx, current_data["u"].shape[0] - 1)
    ti_w = min(time_idx, wind_data["u_wind"].shape[0] - 1)

    # Ocean current interpolation
    u_interp = _build_interpolator(current_data["u"][ti], current_data["lats"], current_data["lons"])
    v_interp = _build_interpolator(current_data["v"][ti], current_data["lats"], current_data["lons"])

    pts = np.column_stack([particle_lats, particle_lons])
    u_curr = u_interp(pts)
    v_curr = v_interp(pts)

    # Wind interpolation
    uw_interp = _build_interpolator(wind_data["u_wind"][ti_w], wind_data["lats"], wind_data["lons"])
    vw_interp = _build_interpolator(wind_data["v_wind"][ti_w], wind_data["lats"], wind_data["lons"])

    u_wind = uw_interp(pts)
    v_wind = vw_interp(pts)

    # Apply wind drift factor with clockwise deflection
    angle_rad = np.radians(WIND_DRIFT_ANGLE_DEG)
    cos_a, sin_a = np.cos(angle_rad), np.sin(angle_rad)

    u_drift = WIND_DRIFT_FACTOR * (cos_a * u_wind + sin_a * v_wind)
    v_drift = WIND_DRIFT_FACTOR * (-sin_a * u_wind + cos_a * v_wind)

    return u_curr + u_drift, v_curr + v_drift


# ─────────────────────────────────────────────────────────────────────────────
# Integration
# ─────────────────────────────────────────────────────────────────────────────

def _velocity_to_deg(u: np.ndarray, v: np.ndarray, lats: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    """Convert velocity (m/s) to degrees/second for lat/lon update."""
    dlat = v / DEG_TO_M_LAT
    dlon = u / (DEG_TO_M_LAT * np.cos(np.radians(lats)))
    return dlat, dlon


def rk4_step(
    particles: ParticleSet,
    current_data: Dict,
    wind_data: Dict,
    time_idx: int,
    dt: float,
) -> None:
    """
    Advance active particles one RK4 timestep.

    Modifies particles.lats and particles.lons in-place.
    Adds random diffusion term after the deterministic step.
    """
    active = particles.active
    lats = particles.lats[active]
    lons = particles.lons[active]
    n = len(lats)
    if n == 0:
        return

    # k1
    u1, v1 = interpolate_velocity(current_data, wind_data, time_idx, lats, lons)
    dlat1, dlon1 = _velocity_to_deg(u1, v1, lats)

    # k2
    lats2 = lats + 0.5 * dt * dlat1
    lons2 = lons + 0.5 * dt * dlon1
    u2, v2 = interpolate_velocity(current_data, wind_data, time_idx, lats2, lons2)
    dlat2, dlon2 = _velocity_to_deg(u2, v2, lats2)

    # k3
    lats3 = lats + 0.5 * dt * dlat2
    lons3 = lons + 0.5 * dt * dlon2
    u3, v3 = interpolate_velocity(current_data, wind_data, time_idx, lats3, lons3)
    dlat3, dlon3 = _velocity_to_deg(u3, v3, lats3)

    # k4
    lats4 = lats + dt * dlat3
    lons4 = lons + dt * dlon3
    u4, v4 = interpolate_velocity(current_data, wind_data, time_idx, lats4, lons4)
    dlat4, dlon4 = _velocity_to_deg(u4, v4, lats4)

    # Combine
    particles.lats[active] += (dt / 6.0) * (dlat1 + 2 * dlat2 + 2 * dlat3 + dlat4)
    particles.lons[active] += (dt / 6.0) * (dlon1 + 2 * dlon2 + 2 * dlon3 + dlon4)

    # Random diffusion
    rng = np.random.RandomState()
    sigma = np.sqrt(2 * HORIZONTAL_DIFFUSIVITY * dt) / DEG_TO_M_LAT
    particles.lats[active] += rng.normal(0, sigma, n)
    particles.lons[active] += rng.normal(0, sigma / np.cos(np.radians(particles.lats[active])), n)


# ─────────────────────────────────────────────────────────────────────────────
# Main simulation runner
# ─────────────────────────────────────────────────────────────────────────────

def run_simulation(
    spill_lat: float,
    spill_lon: float,
    volume_barrels: float = DEFAULT_VOLUME_BARRELS,
    start_time: Optional[datetime] = None,
    duration_hours: int = DEFAULT_FORECAST_HOURS,
    num_particles: int = DEFAULT_NUM_PARTICLES,
    dt: float = DEFAULT_TIMESTEP_SECONDS,
) -> SimulationResult:
    """
    Execute a full oil spill drift simulation.

    1. Initialize particles at spill origin
    2. Fetch environmental data (currents, wind, waves)
    3. Step forward in time with RK4 integration + weathering
    4. Return particle positions, zone boundaries, and heatmap at each timestep
    """
    if start_time is None:
        start_time = datetime.utcnow()

    end_time = start_time + timedelta(hours=duration_hours)
    num_steps = int(duration_hours * 3600 / dt)

    logger.info(
        "Starting simulation: (%.4f, %.4f), %d barrels, %d particles, %dh forecast",
        spill_lat, spill_lon, volume_barrels, num_particles, duration_hours,
    )

    # 1. Initialize particles
    particles = initialize_particles(spill_lat, spill_lon, num_particles, volume_barrels)

    # 2. Fetch environmental data
    current_data = fetch_ocean_currents(spill_lat, spill_lon, start_time, end_time)
    wind_data = fetch_wind_data(spill_lat, spill_lon, start_time, end_time)
    wave_data = fetch_wave_data(spill_lat, spill_lon, start_time, end_time, wind_data)

    # 3. Time-stepping
    timesteps = []

    # Record initial state
    timesteps.append(_snapshot(particles, start_time, 0, volume_barrels))

    for step in range(1, num_steps + 1):
        current_time = start_time + timedelta(seconds=step * dt)
        time_idx = step  # maps to environmental data time index

        # RK4 advection
        rk4_step(particles, current_data, wind_data, time_idx, dt)

        # Weathering (evaporation)
        apply_evaporation(particles, dt, temperature=22.0)

        # Record snapshot every hour
        if step % max(1, int(3600 / dt)) == 0:
            hour = step * dt / 3600
            timesteps.append(_snapshot(particles, current_time, hour, volume_barrels))

    # 4. Build heatmap from final particle positions
    heatmap = compute_particle_density(particles)

    # Environmental data sources
    sources = {
        "currents": current_data.get("source", "unknown"),
        "wind": wind_data.get("source", "unknown"),
        "waves": wave_data.get("source", "unknown"),
    }

    return SimulationResult(
        timesteps=timesteps,
        heatmap=heatmap,
        metadata={
            "spill_lat": spill_lat,
            "spill_lon": spill_lon,
            "volume_barrels": volume_barrels,
            "num_particles": num_particles,
            "duration_hours": duration_hours,
            "data_sources": sources,
        },
    )


def _snapshot(particles: ParticleSet, time: datetime, hour: float, volume: float) -> Dict:
    """Create a snapshot of particle state for API response."""
    active_mask = particles.active
    active_lats = particles.lats[active_mask]
    active_lons = particles.lons[active_mask]
    active_mass = particles.mass[active_mask]

    # Particle list (downsample if too many for JSON)
    max_json = min(len(active_lats), 1000)
    indices = np.linspace(0, len(active_lats) - 1, max_json, dtype=int) if len(active_lats) > 0 else []

    particle_list = []
    for i in indices:
        particle_list.append({
            "lat": round(float(active_lats[i]), 6),
            "lon": round(float(active_lons[i]), 6),
            "mass": round(float(active_mass[i]), 4),
            "active": True,
        })

    # Affected zone (convex hull polygon)
    zone = compute_affected_zone(particles)
    spread_area = compute_spread_area_km2(particles)

    # Stats
    total_active = int(active_mask.sum())
    avg_mass = float(active_mass.mean()) if total_active > 0 else 0
    evaporated_pct = round((1 - avg_mass) * 100, 1)

    return {
        "time": time.isoformat() + "Z" if not time.tzinfo else time.isoformat(),
        "hour": round(hour, 1),
        "particles": particle_list,
        "affected_zone": zone,
        "stats": {
            "active_particles": total_active,
            "total_particles": particles.num_particles,
            "evaporated_pct": evaporated_pct,
            "avg_mass_fraction": round(avg_mass, 4),
            "spread_area_km2": spread_area,
        },
    }
