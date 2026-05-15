/**
 * API Client — communicates with the FastAPI backend.
 * Handles simulation requests, classification, and environmental data.
 */

const API = (() => {
    const BASE_URL = '/api';

    /**
     * Run a full oil spill drift simulation.
     * @param {Object} params - Simulation parameters
     * @returns {Promise<Object>} Simulation results
     */
    async function runSimulation(params) {
        const body = {
            lat: params.lat,
            lon: params.lon,
            volume_barrels: params.volume,
            start_time: params.startTime || new Date().toISOString(),
            duration_hours: params.duration,
            num_particles: params.particles,
        };

        const response = await fetch(`${BASE_URL}/simulate`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });

        if (!response.ok) {
            const err = await response.json().catch(() => ({ detail: 'Unknown error' }));
            throw new Error(err.detail || `HTTP ${response.status}`);
        }

        return response.json();
    }

    /**
     * Run severity classification.
     * @param {Object} metadata - Spill metadata
     * @returns {Promise<Object>} Classification result
     */
    async function classifySeverity(metadata) {
        const response = await fetch(`${BASE_URL}/classify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(metadata),
        });

        if (!response.ok) {
            throw new Error(`Classification failed: HTTP ${response.status}`);
        }

        return response.json();
    }

    /**
     * Get environmental conditions at a location.
     * @param {number} lat
     * @param {number} lon
     * @returns {Promise<Object>}
     */
    async function getEnvironmental(lat, lon) {
        const response = await fetch(`${BASE_URL}/environmental?lat=${lat}&lon=${lon}`);

        if (!response.ok) {
            throw new Error(`Environmental fetch failed: HTTP ${response.status}`);
        }

        return response.json();
    }

    /**
     * Health check.
     * @returns {Promise<Object>}
     */
    async function healthCheck() {
        const response = await fetch(`${BASE_URL}/health`);
        return response.json();
    }

    return { runSimulation, classifySeverity, getEnvironmental, healthCheck };
})();
