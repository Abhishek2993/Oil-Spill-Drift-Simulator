"""
Oil Spill Drift Prediction — FastAPI Application Entry Point.

Serves the API endpoints for simulation, classification, and environmental
data, plus the frontend static files.
"""

import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router as api_router
from backend.config import SERVER_HOST, SERVER_PORT, FRONTEND_DIR

app = FastAPI(
    title="Oil Spill Drift Prediction API",
    description="Real-time oil spill simulation and severity classification",
    version="1.0.0",
)

# ---------------------------------------------------------------------------
# CORS — allow all origins during development
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
app.include_router(api_router, prefix="/api")

# ---------------------------------------------------------------------------
# Serve frontend static files
# ---------------------------------------------------------------------------
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), FRONTEND_DIR)
if os.path.isdir(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

# ---------------------------------------------------------------------------
# Standalone runner
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host=SERVER_HOST,
        port=SERVER_PORT,
        reload=True,
    )
