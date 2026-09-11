import L from "leaflet";
import { GoogleMap, useJsApiLoader } from "@react-google-maps/api";
import { useEffect, useRef } from "react";
import { useWorkflowConfig } from "@/hooks/useWorkflowConfig";

/** Map of cases, planned inspections and government-land polygons.
 *  Google Maps JavaScript API (the platform's primary map library) when VITE_GOOGLE_MAPS_API_KEY is set;
 *  Leaflet + OpenStreetMap otherwise (polygon/geofence work and the no-key sandbox). Both render the same
 *  layers: government-land polygons coloured by agency, case pins coloured by status, planned-inspection
 *  diamonds, and pop-ups that show the case history straight from the map. */
const GOOGLE_KEY = import.meta.env.VITE_GOOGLE_MAPS_API_KEY as string | undefined;
const TILE_URL = "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";
const AGENCY_COLORS: Record<string, string> = { MCG: "#782669", HSVP: "#0d9488", GMDA: "#2563eb", STATE_GOVT: "#f59e0b", PWD: "#7c3aed", IRRIGATION: "#0891b2", FOREST: "#16a34a", PANCHAYAT: "#b45309", RAILWAYS: "#6b7280", NHAI: "#4b5563", DEFENCE: "#374151", OTHER: "#6b7280" };
export const STATUS_PIN: Record<string, string> = {
  DRAFT: "#9ca3af", PENDING_AE: "#2563eb", RETURNED_TO_JE: "#f59e0b", PENDING_JC: "#4338ca", SCN_ISSUED: "#a55cb4", SCN_SERVED: "#782669", RESPONSE_PENDING_AE: "#0e7490", RESPONSE_PENDING_JC: "#0e7490",
  RESPONSE_RECEIVED: "#0e7490", NO_RESPONSE: "#c2410c", HEARING_SCHEDULED: "#6d28d9", ORDER_ISSUED: "#dc2626", ORDER_SERVED: "#b91c1c", APPEAL_STAY: "#334155", EXECUTION_DUE: "#7f1d1d",
  COMPLIED: "#16a34a", EXECUTED: "#15803d", CLOSED: "#6b7280", DROPPED: "#9ca3af", REGULARISED: "#059669",
};
const TASK_PIN: Record<string, string> = { ASSIGNED: "#f59e0b", UNASSIGNED: "#d1d5db", IN_PROGRESS: "#0d9488", VIOLATION_RECORDED: "#dc2626", NO_VIOLATION: "#16a34a", NOT_FOUND: "#6b7280", CANCELLED: "#9ca3af" };
const esc = (v: unknown) => String(v ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c] as string));
const d = (v?: string | null) => (v ? new Date(v).toLocaleDateString("en-IN", { day: "2-digit", month: "2-digit", year: "numeric" }) : "-");
const dt = (v?: string | null) => (v ? new Date(v).toLocaleString("en-IN", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }) : "-");

export function casePopupHtml(p: any): string {
  const hist = (p.history || []).map((h: any) => `<li><span style="color:#6b7280">${dt(h.at)}</span> <b>${esc(h.action).replace(/_/g, " ")}</b>${h.to && h.to !== h.from ? ` → ${esc(h.to).replace(/_/g, " ")}` : ""}${h.remarks ? `<div style="color:#374151">${esc(h.remarks)}</div>` : ""}</li>`).join("");
  const flags = [p.stop_work ? "STOP-WORK" : "", p.sealed ? "SEALED" : "", p.litigation === "STAYED" ? `STAY${p.stay_until ? " till " + d(p.stay_until) : ""}` : ""].filter(Boolean).map((f) => `<span style="background:#fee2e2;color:#b91c1c;border-radius:4px;padding:1px 6px;font-size:10px;margin-right:4px">${f}</span>`).join("");
  return `<div style="min-width:260px;max-width:340px;font-family:inherit">
    <div style="font-weight:700;color:#782669;font-family:monospace">${esc(p.case_no)}</div>
    <div style="font-size:12px">${esc(p.address)}${p.pid ? ` · PID ${esc(p.pid)}` : ""}${p.ward ? ` · Ward ${p.ward}` : ""}</div>
    <div style="margin:4px 0"><span style="background:${STATUS_PIN[p.status] || "#6b7280"};color:#fff;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:600">${esc(p.status_label || p.status)}</span> ${flags}</div>
    <div style="font-size:11px;color:#374151">${(p.violations || []).join(", ")}${p.owner ? ` · ${esc(p.owner)}` : ""}</div>
    ${p.compliance_due_at ? `<div style="font-size:11px;color:#b91c1c">Comply by ${d(p.compliance_due_at)}</div>` : ""}
    <div style="font-size:11px;font-weight:600;margin-top:6px;color:#4a153f">History</div>
    <ul style="font-size:11px;padding-left:14px;margin:2px 0;max-height:150px;overflow:auto">${hist || "<li>-</li>"}</ul>
    <a href="#" data-case-id="${esc(p.id)}" style="display:inline-block;margin-top:6px;color:#0d9488;font-weight:600;font-size:12px">Open case file →</a>
  </div>`;
}
export function taskPopupHtml(p: any): string {
  return `<div style="min-width:220px;font-family:inherit"><div style="font-weight:700;color:#b45309">Planned inspection #${p.id}</div><div style="font-size:12px">${esc(p.address)}${p.pid ? ` · PID ${esc(p.pid)}` : ""}</div>
    <div style="margin:4px 0"><span style="background:${TASK_PIN[p.status] || "#6b7280"};color:#fff;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:600">${esc(p.status_label || p.status)}</span> <span style="font-size:11px">${esc(String(p.category || "").replace(/_/g, " "))}</span></div>
    <div style="font-size:11px;color:#374151">${p.assigned_to ? "Assigned to " + esc(p.assigned_to) : "Unassigned"}${p.due_at ? " · due " + d(p.due_at) : ""}</div>
    ${p.case_id ? `<a href="#" data-case-id="${esc(p.case_id)}" style="display:inline-block;margin-top:6px;color:#0d9488;font-weight:600;font-size:12px">Open case ${esc(p.case_no)} →</a>` : `<a href="#" data-task-id="${p.id}" style="display:inline-block;margin-top:6px;color:#0d9488;font-weight:600;font-size:12px">Open task →</a>`}</div>`;
}
export function parcelPopupHtml(p: any): string {
  const cases = (p.cases || []).map((c: any) => `<li><a href="#" data-case-id="${esc(c.id)}" style="color:#782669;font-family:monospace;font-weight:600">${esc(c.case_no)}</a> <span style="background:${STATUS_PIN[c.status] || "#6b7280"};color:#fff;border-radius:999px;padding:1px 6px;font-size:10px">${esc(c.status).replace(/_/g, " ")}</span><div style="font-size:11px;color:#374151">${esc(c.address)}</div></li>`).join("");
  return `<div style="min-width:240px;max-width:340px;font-family:inherit"><div style="font-weight:700">${esc(p.name || "Government land")}</div><div style="font-size:12px">${esc(p.agency)}${p.land_use ? " · " + esc(p.land_use) : ""}${p.khasra_no ? " · Khasra " + esc(p.khasra_no) : ""}${p.village ? ", " + esc(p.village) : ""}${p.area_sqm ? " · " + Number(p.area_sqm).toFixed(0) + " sq m" : ""}</div>
    <div style="font-size:11px;margin-top:4px"><b>${p.case_count || 0}</b> case(s), <b style="color:#b91c1c">${p.open_case_count || 0}</b> open</div><ul style="font-size:12px;padding-left:14px;margin:4px 0;max-height:160px;overflow:auto">${cases || "<li style='color:#6b7280'>no encroachment case recorded</li>"}</ul></div>`;
}

export interface MapProps {
  center?: [number, number]; zoom?: number; height?: string;
  govtLand?: any; wards?: any; points?: any; onClick?: (lat: number, lng: number) => void;
  marker?: [number, number] | null; fit?: boolean; onPointClick?: (props: any) => void; onOpenCase?: (id: string) => void; onOpenTask?: (id: number) => void; legend?: boolean;
}

/** Pop-up links ("Open case file →") are plain anchors with data attributes; both map engines route them here. */
function usePopupLinks(el: React.RefObject<HTMLElement>, cb: React.MutableRefObject<{ onOpenCase?: MapProps["onOpenCase"]; onOpenTask?: MapProps["onOpenTask"] }>) {
  useEffect(() => {
    const node = el.current;
    if (!node) return;
    const handler = (ev: Event) => {
      const a = (ev.target as HTMLElement).closest("a[data-case-id],a[data-task-id]") as HTMLElement | null;
      if (!a) return;
      ev.preventDefault();
      if (a.dataset.caseId) cb.current.onOpenCase?.(a.dataset.caseId);
      if (a.dataset.taskId) cb.current.onOpenTask?.(Number(a.dataset.taskId));
    };
    node.addEventListener("click", handler);
    return () => node.removeEventListener("click", handler);
  }, [el, cb]);
}

function Legend() {
  const wf = useWorkflowConfig();
  return (
    <div className="absolute bottom-3 left-3 z-[400] card p-2 text-[10px] space-y-1 max-w-[220px] hidden md:block">
      <div className="font-semibold">Case status</div>
      <div className="grid grid-cols-2 gap-x-2">{[["PENDING_JC", `With ${wf.stageShort("AUTHORITY")}`], ["SCN_SERVED", "SCN served"], ["ORDER_SERVED", "Order served"], ["EXECUTION_DUE", "Execution due"], ["APPEAL_STAY", "Stayed"], ["EXECUTED", "Demolished/sealed"], ["CLOSED", "Closed"]].map(([k, l]) => <div key={k} className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: STATUS_PIN[k] }} />{l}</div>)}</div>
      <div className="font-semibold pt-1">Planned inspection ◆</div>
      <div className="grid grid-cols-2 gap-x-2">{[["ASSIGNED", "Assigned"], ["IN_PROGRESS", "On site"], ["VIOLATION_RECORDED", "Violation"], ["NO_VIOLATION", "No violation"]].map(([k, l]) => <div key={k} className="flex items-center gap-1"><span className="inline-block h-2.5 w-2.5 rotate-45" style={{ background: TASK_PIN[k] }} />{l}</div>)}</div>
      <div className="font-semibold pt-1">Government land</div><div>coloured by agency · red fill = open encroachment case</div>
    </div>
  );
}

// ---------------------------------------------------------------- Google Maps (platform default)
function GoogleMapView({ center = [28.4595, 77.0266], zoom = 12, height = "420px", govtLand, wards, points, onClick, marker, fit, onPointClick, onOpenCase, onOpenTask, legend }: MapProps) {
  const { isLoaded } = useJsApiLoader({ id: "mcg-google-maps", googleMapsApiKey: GOOGLE_KEY || "" });
  const wrap = useRef<HTMLDivElement>(null);
  const map = useRef<google.maps.Map | null>(null);
  const layers = useRef<{ land?: google.maps.Data; wards?: google.maps.Data; pts?: google.maps.Data; marker?: google.maps.Marker; info?: google.maps.InfoWindow }>({});
  const cb = useRef({ onOpenCase, onOpenTask, onPointClick, onClick });
  cb.current = { onOpenCase, onOpenTask, onPointClick, onClick };
  usePopupLinks(wrap, cb);

  const openInfo = (html: string, pos: google.maps.LatLng) => {
    const m = map.current; if (!m) return;
    layers.current.info ??= new google.maps.InfoWindow({ maxWidth: 360 });
    layers.current.info.setContent(html);
    layers.current.info.setPosition(pos);
    layers.current.info.open({ map: m });
  };
  const fitTo = (layer: google.maps.Data, maxZoom?: number) => {
    const m = map.current; if (!m) return;
    const b = new google.maps.LatLngBounds();
    let n = 0;
    layer.forEach((f) => f.getGeometry()?.forEachLatLng((ll) => { b.extend(ll); n++; }));
    if (n) { m.fitBounds(b, 20); if (maxZoom) google.maps.event.addListenerOnce(m, "idle", () => { if ((m.getZoom() || 0) > maxZoom) m.setZoom(maxZoom); }); }
  };
  const replace = (key: "land" | "wards" | "pts", geojson: any, style: (f: google.maps.Data.Feature) => google.maps.Data.StyleOptions, popup?: (p: any) => string) => {
    const m = map.current; if (!m) return null;
    layers.current[key]?.setMap(null);
    if (!geojson) { layers.current[key] = undefined; return null; }
    const layer = new google.maps.Data({ map: m });
    layer.addGeoJson(geojson);
    layer.setStyle(style);
    layer.addListener("click", (ev: google.maps.Data.MouseEvent) => {
      const props: any = {}; ev.feature.forEachProperty((v, k) => { props[k] = v; });
      cb.current.onPointClick?.(props);
      if (popup && ev.latLng) openInfo(popup(props), ev.latLng);
    });
    layers.current[key] = layer;
    return layer;
  };

  const renderLayers = () => {
    if (!map.current) return;
    replace("land", govtLand, (f) => {
      const agency = f.getProperty("agency") as string; const open = Number(f.getProperty("open_case_count") || 0);
      return { strokeColor: AGENCY_COLORS[agency] || "#6b7280", strokeWeight: open ? 3 : 1.5, fillOpacity: open ? 0.4 : 0.2, fillColor: open ? "#dc2626" : AGENCY_COLORS[agency] || "#6b7280" };
    }, parcelPopupHtml);
    replace("wards", wards, () => ({ strokeColor: "#0d9488", strokeWeight: 1, fillOpacity: 0.05, fillColor: "#0d9488", clickable: false }));
    const pts = replace("pts", points, (f) => {
      const kind = f.getProperty("kind"); const status = f.getProperty("status") as string;
      if (kind === "task") return { icon: { path: "M 0,-1 1,0 0,1 -1,0 z", scale: 8, fillColor: TASK_PIN[status] || "#f59e0b", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 2 } };
      return { icon: { path: google.maps.SymbolPath.CIRCLE, scale: 8, fillColor: STATUS_PIN[status] || "#782669", fillOpacity: 0.95, strokeColor: "#fff", strokeWeight: 1.5 } };
    }, (p) => (p.kind === "task" ? taskPopupHtml(p) : casePopupHtml(p)));
    if (fit && pts && points?.features?.length) fitTo(pts, 16);
    else if (fit && layers.current.land && govtLand?.features?.length) fitTo(layers.current.land);
  };

  useEffect(() => { renderLayers(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [govtLand, wards, points, fit, isLoaded]);
  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.marker?.setMap(null);
    if (marker) {
      layers.current.marker = new google.maps.Marker({ map: m, position: { lat: marker[0], lng: marker[1] }, icon: { path: google.maps.SymbolPath.CIRCLE, scale: 9, fillColor: "#782669", fillOpacity: 1, strokeColor: "#fff", strokeWeight: 3 } });
      m.panTo({ lat: marker[0], lng: marker[1] }); if ((m.getZoom() || 0) < 16) m.setZoom(16);
    }
  }, [marker]);

  if (!isLoaded) return <div style={{ height }} className="w-full rounded-lg border border-light-border bg-gray-50 flex items-center justify-center text-sm text-light-text-muted">Loading map…</div>;
  return (
    <div className="relative" ref={wrap}>
      <GoogleMap mapContainerStyle={{ height, width: "100%" }} mapContainerClassName="rounded-lg overflow-hidden border border-light-border" center={{ lat: center[0], lng: center[1] }} zoom={zoom}
        options={{ mapTypeControl: false, streetViewControl: false, fullscreenControl: true, clickableIcons: false }}
        onLoad={(m) => { map.current = m; m.addListener("click", (e: google.maps.MapMouseEvent) => { if (e.latLng) cb.current.onClick?.(e.latLng.lat(), e.latLng.lng()); }); renderLayers(); }}
        onUnmount={() => { map.current = null; layers.current = {}; }} />
      {legend && <Legend />}
    </div>
  );
}

// ---------------------------------------------------------------- Leaflet (no API key / polygon work)
function LeafletMapView({ center = [28.4595, 77.0266], zoom = 12, height = "420px", govtLand, wards, points, onClick, marker, fit, onPointClick, onOpenCase, onOpenTask, legend }: MapProps) {
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layers = useRef<{ land?: L.GeoJSON; wards?: L.GeoJSON; pts?: L.GeoJSON; marker?: L.Marker }>({});
  const cb = useRef({ onOpenCase, onOpenTask, onPointClick, onClick });
  cb.current = { onOpenCase, onOpenTask, onPointClick, onClick };
  usePopupLinks(el, cb);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { zoomControl: true }).setView(center, zoom);
    L.tileLayer(TILE_URL, { maxZoom: 20, attribution: "&copy; OpenStreetMap contributors" }).addTo(m);
    m.on("click", (e) => cb.current.onClick?.(e.latlng.lat, e.latlng.lng));
    map.current = m;
    return () => { m.remove(); map.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.land?.remove();
    if (govtLand) {
      layers.current.land = L.geoJSON(govtLand, {
        style: (f) => ({ color: AGENCY_COLORS[f?.properties?.agency] || "#6b7280", weight: f?.properties?.open_case_count ? 3 : 1.5, fillOpacity: f?.properties?.open_case_count ? 0.4 : 0.2, fillColor: f?.properties?.open_case_count ? "#dc2626" : AGENCY_COLORS[f?.properties?.agency] || "#6b7280" }),
        onEachFeature: (f, l) => l.bindPopup(parcelPopupHtml(f.properties), { maxWidth: 360 }),
      }).addTo(m);
      if (fit && govtLand.features?.length && !points?.features?.length) m.fitBounds(layers.current.land.getBounds(), { padding: [20, 20] });
    }
  }, [govtLand, fit, points]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.wards?.remove();
    if (wards) layers.current.wards = L.geoJSON(wards, { style: { color: "#0d9488", weight: 1, fillOpacity: 0.05, dashArray: "4 3" }, onEachFeature: (f, l) => l.bindTooltip(`Ward ${f.properties?.number}`) }).addTo(m);
  }, [wards]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.pts?.remove();
    if (points) {
      layers.current.pts = L.geoJSON(points, {
        pointToLayer: (f, latlng) => {
          const p = f.properties || {};
          if (p.kind === "task") return L.marker(latlng, { icon: L.divIcon({ className: "", html: `<div style="width:14px;height:14px;transform:rotate(45deg);background:${TASK_PIN[p.status] || "#f59e0b"};border:2px solid #fff;box-shadow:0 0 0 1px #6b7280"></div>`, iconSize: [14, 14], iconAnchor: [7, 7] }) });
          return L.circleMarker(latlng, { radius: 8, color: "#fff", weight: 1.5, fillColor: STATUS_PIN[p.status] || "#782669", fillOpacity: 0.95 });
        },
        onEachFeature: (f, l) => { const p = f.properties || {}; l.bindPopup(p.kind === "task" ? taskPopupHtml(p) : casePopupHtml(p), { maxWidth: 360 }); l.on("click", () => cb.current.onPointClick?.(p)); },
      }).addTo(m);
      if (fit && points.features?.length) m.fitBounds(layers.current.pts.getBounds(), { padding: [20, 20], maxZoom: 16 });
    }
  }, [points, fit]);

  useEffect(() => {
    const m = map.current; if (!m) return;
    layers.current.marker?.remove();
    if (marker) { layers.current.marker = L.marker(marker, { icon: L.divIcon({ className: "", html: '<div style="width:18px;height:18px;border-radius:50%;background:#782669;border:3px solid #fff;box-shadow:0 0 0 2px #782669"></div>', iconSize: [18, 18], iconAnchor: [9, 9] }) }).addTo(m); m.setView(marker, Math.max(m.getZoom(), 16)); }
  }, [marker]);

  return (
    <div className="relative">
      <div ref={el} style={{ height }} className="w-full rounded-lg overflow-hidden border border-light-border z-0" />
      {legend && <Legend />}
    </div>
  );
}

export default function MapView(props: MapProps) {
  return GOOGLE_KEY ? <GoogleMapView {...props} /> : <LeafletMapView {...props} />;
}
