"""
API route definitions for the Oil Spill Drift Prediction service.

Endpoints:
    POST /api/simulate       — Run full drift simulation
    POST /api/classify       — Severity classification
    GET  /api/environmental  — Current environmental conditions
    GET  /api/health         — Health check
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Optional

import numpy as np

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.simulation.particle_engine import run_simulation
from backend.simulation.weathering import compute_spread_area_km2
from backend.ml.classifier import get_classifier

logger = logging.getLogger(__name__)
router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Request / Response models
# ─────────────────────────────────────────────────────────────────────────────

class SimulationRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90, description="Spill latitude")
    lon: float = Field(..., ge=-180, le=180, description="Spill longitude")
    volume_barrels: float = Field(5000, ge=10, le=200000, description="Spill volume in barrels")
    start_time: Optional[str] = Field(None, description="ISO 8601 start time (default: now)")
    duration_hours: int = Field(72, ge=1, le=168, description="Forecast duration in hours")
    num_particles: int = Field(500, ge=50, le=2000, description="Number of simulation particles")


class ClassifyRequest(BaseModel):
    volume_barrels: float = Field(5000, ge=10)
    wind_speed: float = Field(5.0, ge=0)
    current_speed: float = Field(0.3, ge=0)
    wave_height: float = Field(1.5, ge=0)
    hours_since_spill: float = Field(6, ge=0)
    water_temperature: float = Field(22.0)
    spread_area_km2: float = Field(10.0, ge=0)


class EnvironmentalRequest(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def health_check():
    """Service health check."""
    return {"status": "ok", "service": "oil-spill-drift-prediction", "version": "1.0.0"}


@router.post("/simulate")
async def simulate(req: SimulationRequest):
    """
    Run a full oil spill drift simulation.

    Returns particle trajectories, affected zone polygons, severity
    classifications, and a density heatmap for each forecast timestep.
    """
    try:
        # Parse start time
        start_time = None
        if req.start_time:
            try:
                start_time = datetime.fromisoformat(req.start_time.replace("Z", "+00:00"))
            except ValueError:
                start_time = datetime.utcnow()
        else:
            start_time = datetime.utcnow()

        logger.info(
            "Simulation request: (%.4f, %.4f), %d bbl, %dh",
            req.lat, req.lon, req.volume_barrels, req.duration_hours,
        )

        # Run simulation
        result = run_simulation(
            spill_lat=req.lat,
            spill_lon=req.lon,
            volume_barrels=req.volume_barrels,
            start_time=start_time,
            duration_hours=req.duration_hours,
            num_particles=req.num_particles,
        )

        # Run severity classification on each timestep
        classifier = get_classifier()
        for ts in result.timesteps:
            meta = {
                "volume_barrels": req.volume_barrels,
                "wind_speed": 5.0,  # average from environmental data
                "current_speed": 0.3,
                "wave_height": 1.5,
                "hours_since_spill": ts["hour"],
                "water_temperature": 22.0,
                "spread_area_km2": ts["stats"].get("active_particles", 0) * 0.02,
            }
            ts["severity"] = classifier.predict(meta)

        sim_id = str(uuid.uuid4())[:8]

        return {
            "simulation_id": sim_id,
            "timesteps": result.timesteps,
            "heatmap": result.heatmap,
            "metadata": result.metadata,
        }

    except Exception as exc:
        logger.exception("Simulation failed")
        raise HTTPException(status_code=500, detail=f"Simulation error: {str(exc)}")


@router.post("/classify")
async def classify(req: ClassifyRequest):
    """
    Run severity classification on spill metadata.

    Returns severity level, confidence, and spread rate estimate.
    """
    try:
        classifier = get_classifier()
        result = classifier.predict(req.model_dump())
        return result
    except Exception as exc:
        logger.exception("Classification failed")
        raise HTTPException(status_code=500, detail=f"Classification error: {str(exc)}")


@router.get("/environmental")
async def environmental(lat: float, lon: float):
    """
    Fetch current environmental conditions for a given lat/lon.

    Returns summary of ocean currents, wind, and wave conditions.
    """
    try:
        from backend.data_fetchers.noaa_erddap import fetch_ocean_currents, fetch_wind_data
        from backend.data_fetchers.copernicus import fetch_wave_data

        now = datetime.utcnow()
        end = now + timedelta(hours=3)

        # Fetch small region
        currents = fetch_ocean_currents(lat, lon, now, end, bbox_size=1.0, grid_points=5)
        wind = fetch_wind_data(lat, lon, now, end, bbox_size=1.0, grid_points=5)
        waves = fetch_wave_data(lat, lon, now, end, wind, bbox_size=1.0, grid_points=5)

        # Extract center values
        mid_lat = len(currents["lats"]) // 2
        mid_lon = len(currents["lons"]) // 2

        u_curr = float(currents["u"][0, mid_lat, mid_lon])
        v_curr = float(currents["v"][0, mid_lat, mid_lon])
        current_speed = round(float(np.sqrt(u_curr**2 + v_curr**2)), 3)

        u_wind = float(wind["u_wind"][0, mid_lat, mid_lon])
        v_wind = float(wind["v_wind"][0, mid_lat, mid_lon])
        wind_speed = round(float(np.sqrt(u_wind**2 + v_wind**2)), 3)
        wind_dir = round(float(np.degrees(np.arctan2(v_wind, u_wind))), 1)

        wave_ht = round(float(waves["wave_height"][0, mid_lat, mid_lon]), 2)



        return {
            "lat": lat,
            "lon": lon,
            "current": {
                "speed_ms": current_speed,
                "u": round(u_curr, 4),
                "v": round(v_curr, 4),
                "source": currents["source"],
            },
            "wind": {
                "speed_ms": wind_speed,
                "direction_deg": wind_dir,
                "source": wind["source"],
            },
            "waves": {
                "height_m": wave_ht,
                "source": waves["source"],
            },
        }

    except Exception as exc:
        logger.exception("Environmental data fetch failed")
        raise HTTPException(status_code=500, detail=f"Environmental data error: {str(exc)}")
