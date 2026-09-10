import L from "leaflet";
import { useEffect, useRef } from "react";

/** Leaflet map (same library as the MCG platform). Loads the government-land layer and case points.
 *  Tiles: OpenStreetMap (swap `TILE_URL` for MCG's own tile server / drone ortho if available). */
const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const AGENCY_COLORS: Record<string, string> = { MCG: "#782669", HSVP: "#0d9488", GMDA: "#2563eb", STATE_GOVT: "#f59e0b", PWD: "#7c3aed", IRRIGATION: "#0891b2", FOREST: "#16a34a", PANCHAYAT: "#b45309", OTHER: "#6b7280" };

export interface MapProps {
  center?: [number, number]; zoom?: number; height?: string;
  govtLand?: any; wards?: any; points?: any; onClick?: (lat: number, lng: number) => void;
  marker?: [number, number] | null; fit?: boolean; onPointClick?: (props: any) => void;
}

export default function MapView({ center = [28.4595, 77.0266], zoom = 12, height = "420px", govtLand, wards, points, onClick, marker, fit, onPointClick }: MapProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layers = useRef<{ land?: L.GeoJSON; wards?: L.GeoJSON; pts?: L.GeoJSON; marker?: L.Marker }>({});

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true }).setView(center, zoom);
    L.tileLayer(TILE_URL, { maxZoom: 20, attribution: "&copy; OpenStreetMap contributors" }).addTo(m);
    m.on("click", (e) => onClick?.(e.latlng.lat, e.latlng.lng));
    map.current = m;
    return () => { m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.land?.remove();
    if (govtLand) {
      layers.current.land = L.geoJSON(govtLand, {
        style: (f) => ({ color: AGENCY_COLORS[f?.properties?.agency] || "#6b7280", weight: 1.5, fillOpacity: 0.25 }),
        onEachFeature: (f, l) => l.bindPopup(`<b>${f.properties?.name || "Govt land"}</b><br>${f.properties?.agency || ""} ${f.properties?.land_use || ""}<br>Khasra ${f.properties?.khasra_no || "-"}, ${f.properties?.village || ""}`),
      }).addTo(m);
      if (fit && govtLand.features?.length) m.fitBounds(layers.current.land.getBounds(), { padding: [20, 20] });
    }
  }, [govtLand, fit]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.wards?.remove();
    if (wards) layers.current.wards = L.geoJSON(wards, { style: { color: "#0d9488", weight: 1, fillOpacity: 0.05, dashArray: "4 3" }, onEachFeature: (f, l) => l.bindTooltip(`Ward ${f.properties?.number}`) }).addTo(m);
  }, [wards]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.pts?.remove();
    if (points) {
      const colors: Record<string, string> = { GOVT_MCG: "#dc2626", GOVT_STATE: "#f97316", PRIVATE: "#782669" };
      layers.current.pts = L.geoJSON(points, {
        pointToLayer: (f, latlng) => L.circleMarker(latlng, { radius: 7, color: "#fff", weight: 1.5, fillColor: colors[f.properties?.land_type] || "#782669", fillOpacity: 0.9 }),
        onEachFeature: (f, l) => { l.bindPopup(`<b>${f.properties?.case_no}</b><br>${f.properties?.address}<br>${f.properties?.status}`); l.on("click", () => onPointClick?.(f.properties)); },
      }).addTo(m);
      if (fit && points.features?.length) m.fitBounds(layers.current.pts.getBounds(), { padding: [20, 20], maxZoom: 16 });
    }
  }, [points, fit, onPointClick]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.marker?.remove();
    if (marker) { layers.current.marker = L.marker(marker, { icon: L.divIcon({ className: "", html: '<div style="width:18px;height:18px;border-radius:50%;background:#782669;border:3px solid #fff;box-shadow:0 0 0 2px #782669"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }) }).addTo(m); m.setView(marker, Math.max(m.getZoom(), 16)); }
  }, [marker]);

  return <div ref={el} style={{ height }} className="w-full rounded-lg overflow-hidden border border-light-border z-0" />;
}
