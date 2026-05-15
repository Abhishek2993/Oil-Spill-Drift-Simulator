/**
 * Map Module — Leaflet.js initialization and layer management.
 * Uses CartoDB Dark Matter tiles for the emergency dashboard aesthetic.
 */

const MapModule = (() => {
    let map = null;
    let originMarker = null;
    let zoneLayer = null;
    let particleCanvasLayer = null;
    let onOriginSetCallback = null;

    // Default center: Gulf of Mexico (Deepwater Horizon area)
    const DEFAULT_CENTER = [28.736, -88.366];
    const DEFAULT_ZOOM = 7;

    /**
     * Initialize the Leaflet map.
     * @param {Function} onOriginSet - Callback when user clicks to set spill origin
     */
    function init(onOriginSet) {
        onOriginSetCallback = onOriginSet;

        map = L.map('map', {
            center: DEFAULT_CENTER,
            zoom: DEFAULT_ZOOM,
            zoomControl: true,
            attributionControl: true,
            preferCanvas: true,
        });

        // Dark tile layer
        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://carto.com/">CARTO</a> &copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
            subdomains: 'abcd',
            maxZoom: 18,
        }).addTo(map);

        // Zone layer group
        zoneLayer = L.layerGroup().addTo(map);

        // Click handler for setting spill origin
        map.on('click', (e) => {
            setOrigin(e.latlng.lat, e.latlng.lng);
            if (onOriginSetCallback) {
                onOriginSetCallback(e.latlng.lat, e.latlng.lng);
            }
        });
    }

    /**
     * Set the spill origin marker on the map.
     */
    function setOrigin(lat, lon) {
        if (originMarker) {
            map.removeLayer(originMarker);
        }

        const icon = L.divIcon({
            className: 'spill-origin-marker',
            html: '<div class="pulse-ring"></div><div class="center-dot"></div>',
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        });

        originMarker = L.marker([lat, lon], { icon }).addTo(map);
        originMarker.bindTooltip(
            `<strong>Spill Origin</strong><br>${lat.toFixed(4)}°, ${lon.toFixed(4)}°`,
            { permanent: false, direction: 'top', offset: [0, -16] }
        );
    }

    /**
     * Update the affected zone polygon.
     * @param {Object} geoJson - GeoJSON polygon
     */
    function updateZone(geoJson) {
        zoneLayer.clearLayers();

        if (!geoJson || !geoJson.coordinates || geoJson.coordinates.length === 0) return;

        try {
            const polygon = L.geoJSON(geoJson, {
                style: {
                    color: '#ff6b35',
                    weight: 2,
                    opacity: 0.8,
                    fillColor: '#ff6b35',
                    fillOpacity: 0.08,
                    dashArray: '6, 4',
                },
            });
            zoneLayer.addLayer(polygon);
        } catch (e) {
            console.warn('Failed to render zone polygon:', e);
        }
    }

    /**
     * Toggle zone layer visibility.
     */
    function toggleZone(visible) {
        if (visible) {
            map.addLayer(zoneLayer);
        } else {
            map.removeLayer(zoneLayer);
        }
    }

    /**
     * Get the map instance.
     */
    function getMap() {
        return map;
    }

    /**
     * Fit map bounds to show all particles.
     */
    function fitToParticles(particles) {
        if (!particles || particles.length === 0) return;

        const lats = particles.map(p => p.lat);
        const lons = particles.map(p => p.lon);

        const bounds = [
            [Math.min(...lats) - 0.2, Math.min(...lons) - 0.2],
            [Math.max(...lats) + 0.2, Math.max(...lons) + 0.2],
        ];

        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    }

    return { init, setOrigin, updateZone, toggleZone, getMap, fitToParticles };
})();
