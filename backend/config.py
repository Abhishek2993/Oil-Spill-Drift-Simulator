"""
Configuration constants for the Oil Spill Drift Prediction application.
Contains API endpoints, simulation defaults, and physical constants.
"""

# =============================================================================
# NOAA ERDDAP Configuration
# =============================================================================

# OSCAR Ocean Surface Currents (u, v velocity components)
ERDDAP_OSCAR_BASE = "https://coastwatch.pfeg.noaa.gov/erddap/griddap"
ERDDAP_OSCAR_DATASET = "jplOscar_LonPM180"
OSCAR_VARIABLES = ["u", "v"]

# GFS Global Forecast System Wind (10m wind components)
ERDDAP_GFS_BASE = "https://oos.soest.hawaii.edu/erddap/griddap"
ERDDAP_GFS_DATASET = "ncep_global"
GFS_VARIABLES = ["ugrd10m", "vgrd10m"]

# =============================================================================
# Copernicus Marine Service Configuration
# =============================================================================

CMEMS_PRODUCT_ID = "GLOBAL_ANALYSISFORECAST_PHY_001_024"
CMEMS_WAVE_DATASET = "cmems_mod_glo_wav_anfc_0.083deg_PT3H-i"
CMEMS_WAVE_VARIABLES = ["VHM0", "VMDR", "VTPK"]  # Wave height, direction, period

# =============================================================================
# Simulation Defaults
# =============================================================================

DEFAULT_NUM_PARTICLES = 500
DEFAULT_TIMESTEP_SECONDS = 3600        # 1 hour
DEFAULT_FORECAST_HOURS = 72            # 3 days
DEFAULT_VOLUME_BARRELS = 5000
DEFAULT_BBOX_SIZE_DEG = 3.0            # Bounding box around spill for data fetch

# =============================================================================
# Physical Constants
# =============================================================================

# Wind drift factor: oil surface drift is typically 3-4% of wind speed
WIND_DRIFT_FACTOR = 0.035

# Wind drift deflection angle (degrees clockwise from wind direction)
# Ekman-like deflection for surface oil
WIND_DRIFT_ANGLE_DEG = 15.0

# Horizontal diffusivity coefficient (m²/s)
# Typical range for open ocean: 1-100 m²/s
HORIZONTAL_DIFFUSIVITY = 10.0

# Earth radius in meters (for lat/lon to meter conversions)
EARTH_RADIUS_M = 6371000.0

# Degrees to meters conversion at equator
DEG_TO_M_LAT = 111320.0

# =============================================================================
# Evaporation / Weathering Constants
# =============================================================================

# Evaporation rate constant (1/s) for light crude oil
# Calibrated so ~40% evaporates in first 24 hours at 20°C
EVAPORATION_RATE_K = 5.8e-6

# Temperature adjustment factor for evaporation
EVAPORATION_TEMP_FACTOR = 0.045  # per °C above reference

# Reference temperature for evaporation (°C)
EVAPORATION_REF_TEMP = 20.0

# Minimum mass fraction before particle is deactivated
MIN_MASS_FRACTION = 0.05

# =============================================================================
# ML Classifier
# =============================================================================

MODEL_PATH = "backend/ml/model.joblib"
SEVERITY_LABELS = ["low", "moderate", "high"]

# =============================================================================
# Server Configuration
# =============================================================================

SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
FRONTEND_DIR = "frontend"
