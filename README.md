# Oil Spill Drift Tracker — Real-time Prediction & Visualization

An advanced emergency-response decision support system designed to simulate and visualize the trajectory of oil spills in real-time. Built with a high-performance Python backend and an interactive JavaScript dashboard.

##  Core Functionality

- **Live Data Integration**: Fetches real-time ocean current, wind, and wave data from **NOAA ERDDAP** (OSCAR/GFS) and **Copernicus Marine Service**.
- **Lagrangian Particle Tracking**: Implements a physics-based simulation engine using 4th-order Runge-Kutta (RK4) integration to predict particle drift.
- **Weathering & Evaporation**: Models oil decay over time using exponential evaporation curves based on environmental temperature and oil type.
- **ML Severity Assessment**: Uses a **Random Forest classifier** trained on physics-informed synthetic data to estimate spill severity (Low, Moderate, High) and spread rates.
- **Interactive Map Dashboard**: High-performance canvas rendering on Leaflet.js for smooth animation of thousands of particles.

##  Technology Stack

### Backend
- **FastAPI**: Modern, high-performance web framework.
- **NumPy & SciPy**: Heavy lifting for particle physics and spatial interpolation.
- **scikit-learn**: Machine learning inference for severity prediction.
- **Requests**: REST API communication with oceanographic data providers.

### Frontend
- **Leaflet.js**: Interactive mapping foundation.
- **HTML5 Canvas**: High-frequency rendering for particle trajectories.
- **Vanilla CSS**: Premium dark-themed emergency response interface.

##  How It Works

### 1. Data Fetching
When a simulation is triggered, the backend queries the **NOAA ERDDAP** servers for the specific geographic domain. It retrieves:
- **Zonal (U) and Meridional (V) currents** from the OSCAR dataset.
- **10-meter wind vectors** from the GFS global forecast.
*If the external APIs are unreachable, the system automatically switches to a physics-based synthetic data generator to maintain functionality.*

### 2. Simulation Engine
The system initializes $N$ particles at the spill origin. For each timestep ($dt=1hr$):
- **Advection**: Particles move according to the sum of ocean currents and a wind drift factor (typically 3.5% of wind speed with a 15° Ekman-like deflection).
- **Diffusion**: A random-walk term is added to simulate horizontal diffusivity ($K_h \approx 10 m^2/s$).
- **Integration**: Uses **RK4** for high spatial accuracy.

### 3. Weathering (Evaporation)
The mass of each particle is reduced at every step using an exponential decay model:
$$M(t) = M(0) \cdot e^{-k \cdot t}$$
where $k$ is adjusted based on water temperature. Particles with less than 5% mass are deactivated.

### 4. Severity Assessment
The **Random Forest** model analyzes:
- Spill volume and duration.
- Environmental energy (wind/wave height).
- Spread area (computed via Convex Hull).
- Evaporation rate.
It provides a probability distribution across severity levels to assist decision-makers.

##  Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/Abhishek2993/Oil-Spill-Drift-Simulator.git
   cd Oil-Spill-Drift-Simulator
   ```

2. **Set up Python Environment**:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r backend/requirements.txt
   ```

3. **Train the ML Model** (Initial setup):
   ```bash
   python -m backend.ml.train_model
   ```

4. **Run the Application**:
   ```bash
   python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
   ```

5. **Open Dashboard**:
   Navigate to [http://localhost:8000](http://localhost:8000).

##  API Endpoints

- `POST /api/simulate`: Runs a full 72-hour drift simulation.
- `POST /api/classify`: Predicts severity based on spill metadata.
- `GET /api/environmental`: Fetches live conditions for a specific lat/lon.
- `GET /api/health`: System status check.

## ⚖️ License
This project is for emergency response research and educational purposes. Use with official NOAA/Copernicus data for operational decisions.
