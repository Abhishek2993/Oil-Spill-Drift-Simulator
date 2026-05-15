/**
 * App Module — Main application orchestrator.
 * Wires together Map, Particles, Heatmap, Controls, and API modules.
 */
const App = (() => {
    let simulationData = null;

    function init() {
        // Initialize map
        MapModule.init(onOriginSet);

        // Initialize renderer layers
        const map = MapModule.getMap();
        ParticleRenderer.init(map);
        HeatmapModule.init(map);

        // Initialize controls
        Controls.init(onSimulate);

        // Layer toggles
        document.getElementById('toggle-particles').addEventListener('change', (e) => {
            ParticleRenderer.setVisible(e.target.checked);
        });
        document.getElementById('toggle-heatmap').addEventListener('change', (e) => {
            HeatmapModule.setVisible(e.target.checked);
            if (e.target.checked && simulationData) {
                const ts = ParticleRenderer.getCurrentTimestep();
                if (ts) HeatmapModule.updateFromParticles(ts.particles);
            }
        });
        document.getElementById('toggle-zone').addEventListener('change', (e) => {
            MapModule.toggleZone(e.target.checked);
        });
        document.getElementById('toggle-trails').addEventListener('change', (e) => {
            ParticleRenderer.setTrails(e.target.checked);
        });

        // Timeline controls
        document.getElementById('btn-play').addEventListener('click', startPlayback);
        document.getElementById('btn-pause').addEventListener('click', pausePlayback);
        document.getElementById('btn-reset').addEventListener('click', resetPlayback);

        document.getElementById('timeline-scrubber').addEventListener('input', (e) => {
            const frame = parseInt(e.target.value);
            ParticleRenderer.setFrame(frame);
            _updateTimelineDisplay(frame);
            _updateVisuals(frame);
        });

        document.getElementById('playback-speed').addEventListener('change', (e) => {
            ParticleRenderer.setSpeed(parseFloat(e.target.value));
        });

        // Health check
        API.healthCheck()
            .then(() => Controls.setSystemStatus('', 'System Ready'))
            .catch(() => Controls.setSystemStatus('error', 'Backend Offline'));

        console.log('[OilSpill] Dashboard initialized');
    }

    function onOriginSet(lat, lon) {
        Controls.setCoordinates(lat, lon);
    }

    async function onSimulate(params) {
        if (!params.lat || !params.lon) {
            alert('Please set a spill origin by clicking on the map.');
            return;
        }

        Controls.setLoading(true);
        Controls.setSystemStatus('simulating', 'Simulating...');
        Controls.setLoadingText('Fetching environmental data...');

        try {
            Controls.setLoadingText('Running particle simulation...');
            const data = await API.runSimulation(params);
            simulationData = data;

            Controls.setLoadingText('Rendering results...');

            // Load particle timesteps
            ParticleRenderer.loadTimesteps(data.timesteps);

            // Show timeline
            const timeline = document.getElementById('timeline-container');
            timeline.classList.remove('hidden');

            // Hide map overlay hint
            const overlay = document.getElementById('map-overlay-info');
            if (overlay) overlay.classList.add('hidden');

            // Configure timeline scrubber
            const scrubber = document.getElementById('timeline-scrubber');
            scrubber.max = data.timesteps.length - 1;
            scrubber.value = 0;

            // Build timeline markers
            _buildTimelineMarkers(data.timesteps);

            // Set origin marker
            MapModule.setOrigin(params.lat, params.lon);

            // Update initial frame visuals
            _updateVisuals(0);

            // Fit map to particles
            if (data.timesteps.length > 0) {
                const lastTs = data.timesteps[data.timesteps.length - 1];
                MapModule.fitToParticles(lastTs.particles);
            }

            // Update data sources
            if (data.metadata && data.metadata.data_sources) {
                Controls.updateDataSources(data.metadata.data_sources);
            }

            Controls.setSystemStatus('', 'Simulation Complete');

        } catch (err) {
            console.error('Simulation failed:', err);
            Controls.setSystemStatus('error', 'Simulation Failed');
            alert('Simulation failed: ' + err.message);
        } finally {
            Controls.setLoading(false);
        }
    }

    function startPlayback() {
        document.getElementById('btn-play').classList.add('hidden');
        document.getElementById('btn-pause').classList.remove('hidden');
        ParticleRenderer.play(parseFloat(document.getElementById('playback-speed').value));
        _animateTimeline();
    }

    function pausePlayback() {
        document.getElementById('btn-play').classList.remove('hidden');
        document.getElementById('btn-pause').classList.add('hidden');
        ParticleRenderer.pause();
    }

    function resetPlayback() {
        pausePlayback();
        ParticleRenderer.reset();
        document.getElementById('timeline-scrubber').value = 0;
        _updateTimelineDisplay(0);
        if (simulationData) _updateVisuals(0);
    }

    function onPlaybackEnd() {
        pausePlayback();
    }

    let timelineAnimId = null;
    function _animateTimeline() {
        if (!ParticleRenderer.isPlaying()) {
            cancelAnimationFrame(timelineAnimId);
            return;
        }

        const frame = ParticleRenderer.getCurrentFrameIndex();
        document.getElementById('timeline-scrubber').value = frame;
        _updateTimelineDisplay(frame);
        _updateVisuals(frame);

        timelineAnimId = requestAnimationFrame(_animateTimeline);
    }

    function _updateTimelineDisplay(frame) {
        if (!simulationData || !simulationData.timesteps[frame]) return;
        const ts = simulationData.timesteps[frame];
        document.getElementById('timeline-time').textContent = `T+${ts.hour}h`;
    }

    function _updateVisuals(frame) {
        if (!simulationData || !simulationData.timesteps[frame]) return;
        const ts = simulationData.timesteps[frame];

        // Update heatmap
        if (HeatmapModule.isVisible() && ts.particles) {
            HeatmapModule.updateFromParticles(ts.particles);
        }

        // Update affected zone
        if (ts.affected_zone) {
            MapModule.updateZone(ts.affected_zone);
        }

        // Update severity
        if (ts.severity) {
            Controls.updateSeverity(ts.severity);
        }

        // Update stats
        Controls.updateStats({
            active_particles: ts.stats?.active_particles,
            evaporated_pct: ts.stats?.evaporated_pct,
            spread_area: ts.stats?.spread_area_km2 !== undefined
                ? ts.stats.spread_area_km2.toFixed(1) + ' km²'
                : '—',
            hour: ts.hour,
        });
    }

    function _buildTimelineMarkers(timesteps) {
        const container = document.getElementById('timeline-markers');
        container.innerHTML = '';
        const total = timesteps.length;
        // Show markers at key intervals
        const interval = Math.max(1, Math.floor(total / 6));
        for (let i = 0; i < total; i += interval) {
            const pct = (i / (total - 1)) * 100;
            const marker = document.createElement('div');
            marker.style.cssText = `
                position: absolute; left: ${pct}%; top: -2px;
                transform: translateX(-50%);
                font-size: 9px; color: #5a6478;
                font-family: var(--font-mono);
            `;
            marker.textContent = timesteps[i].hour + 'h';
            container.appendChild(marker);
        }
    }

    // Expose for particle renderer callback
    window.App = { onPlaybackEnd };

    // Init on DOM ready
    document.addEventListener('DOMContentLoaded', init);

    return { init, onPlaybackEnd };
})();
