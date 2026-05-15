/**
 * Particle Renderer — Canvas overlay for high-performance particle visualization.
 * 
 * Uses an HTML5 canvas positioned over the Leaflet map to render particles
 * with smooth interpolation between simulation timesteps, color coding by
 * mass fraction, and optional trail effects.
 */

const ParticleRenderer = (() => {
    let canvas = null;
    let ctx = null;
    let map = null;
    let visible = true;
    let showTrails = true;

    // Simulation data
    let timesteps = [];
    let currentFrame = 0;

    // Animation state
    let animating = false;
    let animFrameId = null;
    let playbackSpeed = 1;
    let interpFactor = 0;

    // Trail buffer
    let trailCanvas = null;
    let trailCtx = null;

    // Color stops: mass fraction → [r, g, b]
    // Fresh oil (high mass) = bright orange, weathered (low mass) = dark red/brown
    const COLOR_STOPS = [
        { stop: 1.0, color: [255, 140, 50] },   // bright orange
        { stop: 0.7, color: [255, 90, 30] },     // deep orange
        { stop: 0.4, color: [220, 50, 30] },     // red
        { stop: 0.1, color: [120, 30, 20] },     // dark brown-red
    ];

    /**
     * Initialize the canvas overlay on the Leaflet map.
     */
    function init(leafletMap) {
        map = leafletMap;

        // Create main canvas
        canvas = document.createElement('canvas');
        canvas.id = 'particle-canvas';
        canvas.style.cssText = `
            position: absolute; top: 0; left: 0;
            width: 100%; height: 100%;
            pointer-events: none; z-index: 400;
        `;
        map.getContainer().appendChild(canvas);
        ctx = canvas.getContext('2d');

        // Create trail canvas (behind main)
        trailCanvas = document.createElement('canvas');
        trailCanvas.id = 'trail-canvas';
        trailCanvas.style.cssText = `
            position: absolute; top: 0; left: 0;
            width: 100%; height: 100%;
            pointer-events: none; z-index: 399;
        `;
        map.getContainer().appendChild(trailCanvas);
        trailCtx = trailCanvas.getContext('2d');

        // Resize on window resize and map move
        _resize();
        window.addEventListener('resize', _resize);
        map.on('move zoom resize', _redraw);
        map.on('moveend zoomend', _redraw);
    }

    function _resize() {
        const container = map.getContainer();
        const w = container.clientWidth;
        const h = container.clientHeight;
        const dpr = window.devicePixelRatio || 1;

        canvas.width = w * dpr;
        canvas.height = h * dpr;
        ctx.scale(dpr, dpr);

        trailCanvas.width = w * dpr;
        trailCanvas.height = h * dpr;
        trailCtx.scale(dpr, dpr);

        _redraw();
    }

    /**
     * Load simulation timesteps for rendering.
     * @param {Array} ts - Array of timestep objects with particles array
     */
    function loadTimesteps(ts) {
        timesteps = ts;
        currentFrame = 0;
        interpFactor = 0;
        clearTrails();
        _redraw();
    }

    /**
     * Set the current frame index (from timeline scrubber).
     */
    function setFrame(frameIndex) {
        currentFrame = Math.max(0, Math.min(frameIndex, timesteps.length - 1));
        interpFactor = 0;
        _redraw();
    }

    /**
     * Get current frame data.
     */
    function getCurrentTimestep() {
        if (timesteps.length === 0) return null;
        return timesteps[currentFrame];
    }

    /**
     * Start animated playback.
     */
    function play(speed = 1) {
        playbackSpeed = speed;
        if (animating) return;
        animating = true;
        _animate();
    }

    /**
     * Pause playback.
     */
    function pause() {
        animating = false;
        if (animFrameId) {
            cancelAnimationFrame(animFrameId);
            animFrameId = null;
        }
    }

    /**
     * Reset to first frame.
     */
    function reset() {
        pause();
        currentFrame = 0;
        interpFactor = 0;
        clearTrails();
        _redraw();
    }

    function setSpeed(speed) {
        playbackSpeed = speed;
    }

    function setVisible(v) {
        visible = v;
        canvas.style.display = v ? 'block' : 'none';
    }

    function setTrails(v) {
        showTrails = v;
        trailCanvas.style.display = v ? 'block' : 'none';
        if (!v) clearTrails();
    }

    function clearTrails() {
        if (trailCtx) {
            trailCtx.clearRect(0, 0, trailCanvas.width, trailCanvas.height);
        }
    }

    function getFrameCount() {
        return timesteps.length;
    }

    function getCurrentFrameIndex() {
        return currentFrame;
    }

    function isPlaying() {
        return animating;
    }

    // ─── Animation loop ───
    let lastTime = 0;
    function _animate(timestamp) {
        if (!animating) return;

        const dt = timestamp - (lastTime || timestamp);
        lastTime = timestamp;

        // Advance interpolation
        interpFactor += (dt / 1000) * playbackSpeed * 0.5; // 0.5 = half-second per frame

        if (interpFactor >= 1) {
            interpFactor = 0;
            currentFrame++;

            if (currentFrame >= timesteps.length - 1) {
                currentFrame = timesteps.length - 1;
                animating = false;
                // Notify app that playback ended
                if (window.App && window.App.onPlaybackEnd) {
                    window.App.onPlaybackEnd();
                }
                _redraw();
                return;
            }

            // Draw trail snapshot
            if (showTrails) {
                _drawTrail();
            }
        }

        _redraw();
        animFrameId = requestAnimationFrame(_animate);
    }

    function _drawTrail() {
        if (!timesteps[currentFrame]) return;
        const particles = timesteps[currentFrame].particles;
        if (!particles) return;

        const dpr = window.devicePixelRatio || 1;

        // Fade existing trails
        trailCtx.save();
        trailCtx.setTransform(1, 0, 0, 1, 0, 0);
        trailCtx.globalCompositeOperation = 'destination-out';
        trailCtx.fillStyle = 'rgba(0, 0, 0, 0.03)';
        trailCtx.fillRect(0, 0, trailCanvas.width, trailCanvas.height);
        trailCtx.restore();

        trailCtx.globalCompositeOperation = 'source-over';

        for (const p of particles) {
            const point = map.latLngToContainerPoint([p.lat, p.lon]);
            const [r, g, b] = _massToColor(p.mass);
            trailCtx.beginPath();
            trailCtx.arc(point.x, point.y, 1.5, 0, Math.PI * 2);
            trailCtx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.15)`;
            trailCtx.fill();
        }
    }

    function _redraw() {
        if (!ctx || timesteps.length === 0) return;

        const dpr = window.devicePixelRatio || 1;
        const w = canvas.width / dpr;
        const h = canvas.height / dpr;
        ctx.clearRect(0, 0, w, h);

        if (!visible) return;

        const frame = timesteps[currentFrame];
        const nextFrame = timesteps[Math.min(currentFrame + 1, timesteps.length - 1)];

        if (!frame || !frame.particles) return;

        const particles = frame.particles;
        const nextParticles = nextFrame ? nextFrame.particles : null;

        for (let i = 0; i < particles.length; i++) {
            const p = particles[i];
            let lat = p.lat;
            let lon = p.lon;

            // Interpolate to next frame for smooth animation
            if (nextParticles && i < nextParticles.length && interpFactor > 0) {
                lat = p.lat + (nextParticles[i].lat - p.lat) * interpFactor;
                lon = p.lon + (nextParticles[i].lon - p.lon) * interpFactor;
            }

            const point = map.latLngToContainerPoint([lat, lon]);
            const [r, g, b] = _massToColor(p.mass);
            const radius = 2 + p.mass * 2; // bigger when fresh
            const alpha = 0.3 + p.mass * 0.6;

            // Glow effect
            ctx.beginPath();
            ctx.arc(point.x, point.y, radius + 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha * 0.15})`;
            ctx.fill();

            // Core dot
            ctx.beginPath();
            ctx.arc(point.x, point.y, radius, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(${r}, ${g}, ${b}, ${alpha})`;
            ctx.fill();
        }
    }

    function _massToColor(mass) {
        for (let i = 0; i < COLOR_STOPS.length - 1; i++) {
            if (mass >= COLOR_STOPS[i + 1].stop) {
                const t = (mass - COLOR_STOPS[i + 1].stop) /
                          (COLOR_STOPS[i].stop - COLOR_STOPS[i + 1].stop);
                return [
                    Math.round(COLOR_STOPS[i + 1].color[0] + t * (COLOR_STOPS[i].color[0] - COLOR_STOPS[i + 1].color[0])),
                    Math.round(COLOR_STOPS[i + 1].color[1] + t * (COLOR_STOPS[i].color[1] - COLOR_STOPS[i + 1].color[1])),
                    Math.round(COLOR_STOPS[i + 1].color[2] + t * (COLOR_STOPS[i].color[2] - COLOR_STOPS[i + 1].color[2])),
                ];
            }
        }
        const last = COLOR_STOPS[COLOR_STOPS.length - 1];
        return last.color;
    }

    return {
        init, loadTimesteps, setFrame, getCurrentTimestep,
        play, pause, reset, setSpeed,
        setVisible, setTrails, clearTrails,
        getFrameCount, getCurrentFrameIndex, isPlaying,
    };
})();
