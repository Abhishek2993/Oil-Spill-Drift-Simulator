/**
 * Heatmap Module — Leaflet.heat integration for risk visualization.
 */
const HeatmapModule = (() => {
    let heatLayer = null;
    let map = null;
    let visible = true;

    const GRADIENT = {
        0.0: 'rgba(0,0,0,0)', 0.2: '#064e3b', 0.35: '#22c55e',
        0.5: '#eab308', 0.7: '#f97316', 0.85: '#ef4444', 1.0: '#dc2626',
    };

    function init(leafletMap) { map = leafletMap; }

    function updateFromParticles(particles) {
        if (!map || !particles || !particles.length) return;
        _clear();
        if (!visible) return;
        const data = particles.map(p => [p.lat, p.lon, p.mass * 0.8 + 0.2]);
        heatLayer = L.heatLayer(data, {
            radius: 25, blur: 20, maxZoom: 12, max: 1.0, minOpacity: 0.15, gradient: GRADIENT
        }).addTo(map);
    }

    function updateFromGrid(hd) {
        if (!map || !hd || !hd.grid || !hd.grid.length) return;
        _clear();
        if (!visible) return;
        const { bounds, grid, rows, cols } = hd;
        const [[latMin, lonMin], [latMax, lonMax]] = bounds;
        const dLat = (latMax - latMin) / rows, dLon = (lonMax - lonMin) / cols;
        const data = [];
        for (let i = 0; i < rows; i++)
            for (let j = 0; j < cols; j++)
                if (grid[i][j] > 0.01)
                    data.push([latMin + (i + 0.5) * dLat, lonMin + (j + 0.5) * dLon, grid[i][j]]);
        if (!data.length) return;
        heatLayer = L.heatLayer(data, {
            radius: 20, blur: 18, maxZoom: 12, max: 1.0, minOpacity: 0.1, gradient: GRADIENT
        }).addTo(map);
    }

    function setVisible(v) {
        visible = v;
        if (!v) _clear();
    }

    function _clear() {
        if (heatLayer) { map.removeLayer(heatLayer); heatLayer = null; }
    }

    function clear() { _clear(); }
    function isVisible() { return visible; }

    return { init, updateFromParticles, updateFromGrid, setVisible, clear, isVisible };
})();
