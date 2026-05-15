/**
 * Controls Module — UI controls and form handling for spill parameters.
 */
const Controls = (() => {
    let duration = 72;
    let onSimulateCallback = null;

    function init(onSimulate) {
        onSimulateCallback = onSimulate;
        _bindInputs();
        _bindDurationButtons();
        _bindSimulateButton();
        _startClock();
    }

    function setCoordinates(lat, lon) {
        document.getElementById('input-lat').value = lat.toFixed(4);
        document.getElementById('input-lon').value = lon.toFixed(4);
    }

    function getParams() {
        return {
            lat: parseFloat(document.getElementById('input-lat').value),
            lon: parseFloat(document.getElementById('input-lon').value),
            volume: parseInt(document.getElementById('input-volume').value),
            duration: duration,
            particles: parseInt(document.getElementById('input-particles').value),
        };
    }

    function setLoading(loading) {
        const btn = document.getElementById('btn-simulate');
        const overlay = document.getElementById('loading-overlay');
        btn.disabled = loading;
        overlay.classList.toggle('hidden', !loading);
    }

    function setLoadingText(text) {
        const sub = document.getElementById('loading-sub');
        if (sub) sub.textContent = text;
    }

    function updateSeverity(data) {
        if (!data) return;
        const badge = document.getElementById('severity-badge');
        badge.textContent = data.severity.toUpperCase();
        badge.className = 'severity-badge ' + data.severity;

        document.getElementById('severity-confidence').textContent =
            `Confidence: ${(data.confidence * 100).toFixed(1)}%`;

        if (data.probabilities) {
            const p = data.probabilities;
            _setBar('low', p.low);
            _setBar('moderate', p.moderate);
            _setBar('high', p.high);
        }

        document.getElementById('spread-value').textContent =
            `${data.spread_rate_km2_hr} km²/hr`;
    }

    function updateStats(stats) {
        if (!stats) return;
        document.getElementById('stat-active').textContent = stats.active_particles || '—';
        document.getElementById('stat-evaporated').textContent =
            stats.evaporated_pct !== undefined ? stats.evaporated_pct + '%' : '—';
        document.getElementById('stat-area').textContent =
            stats.spread_area || '—';
        document.getElementById('stat-hour').textContent =
            stats.hour !== undefined ? 'T+' + stats.hour + 'h' : '—';
    }

    function updateDataSources(sources) {
        if (!sources) return;
        ['currents', 'wind', 'waves'].forEach(key => {
            const tag = document.getElementById('tag-' + key);
            if (tag && sources[key]) {
                tag.classList.add('active');
                tag.title = sources[key];
            }
        });
    }

    function setSystemStatus(status, text) {
        const badge = document.getElementById('system-status');
        badge.className = 'status-badge ' + status;
        badge.querySelector('.status-text').textContent = text;
    }

    // ─── Private ───
    function _setBar(level, value) {
        const fill = document.getElementById('bar-' + level);
        const pct = document.getElementById('pct-' + level);
        if (fill) fill.style.width = (value * 100) + '%';
        if (pct) pct.textContent = (value * 100).toFixed(1) + '%';
    }

    function _bindInputs() {
        // Sync range and number inputs
        _syncInputs('input-volume-range', 'input-volume');
        _syncInputs('input-particles-range', 'input-particles');
    }

    function _syncInputs(rangeId, numberId) {
        const range = document.getElementById(rangeId);
        const num = document.getElementById(numberId);
        if (!range || !num) return;
        range.addEventListener('input', () => { num.value = range.value; });
        num.addEventListener('input', () => { range.value = num.value; });
    }

    function _bindDurationButtons() {
        document.querySelectorAll('.dur-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.dur-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                duration = parseInt(btn.dataset.hours);
            });
        });
    }

    function _bindSimulateButton() {
        document.getElementById('btn-simulate').addEventListener('click', () => {
            if (onSimulateCallback) onSimulateCallback(getParams());
        });
    }

    function _startClock() {
        const el = document.getElementById('clock');
        function tick() {
            const now = new Date();
            el.textContent = now.toUTCString().slice(17, 25) + ' UTC';
        }
        tick();
        setInterval(tick, 1000);
    }

    return {
        init, setCoordinates, getParams, setLoading, setLoadingText,
        updateSeverity, updateStats, updateDataSources, setSystemStatus,
    };
})();
