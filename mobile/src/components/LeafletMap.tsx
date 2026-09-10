import { useMemo } from "react";
import { WebView } from "react-native-webview";

/** Leaflet inside a WebView - identical to the map used by the MCG HARYANA app; works on iOS and
 *  Android without any Google Maps key. Government-land polygons + case points + optional marker. */
export default function LeafletMap({ govtLand, points, marker, onPointPress, onMapPress, center = [28.4595, 77.0266], zoom = 12 }: { govtLand?: any; points?: any; marker?: [number, number] | null; onPointPress?: (p: any) => void; onMapPress?: (lat: number, lng: number) => void; center?: [number, number]; zoom?: number }) {
  const html = useMemo(() => `<!doctype html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/><script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script><style>html,body,#m{height:100%;margin:0}</style></head><body><div id="m"></div><script>
const map=L.map('m').setView(${JSON.stringify(center)},${zoom});L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:20,attribution:'&copy; OpenStreetMap contributors'}).addTo(map);
const colors={MCG:'#782669',HSVP:'#0d9488',GMDA:'#2563eb',STATE_GOVT:'#f59e0b',PWD:'#7c3aed',IRRIGATION:'#0891b2',FOREST:'#16a34a',PANCHAYAT:'#b45309',OTHER:'#6b7280'};
const land=${JSON.stringify(govtLand || null)};const pts=${JSON.stringify(points || null)};const marker=${JSON.stringify(marker || null)};
if(land){L.geoJSON(land,{style:f=>({color:colors[f.properties.agency]||'#6b7280',weight:1.5,fillOpacity:.25}),onEachFeature:(f,l)=>l.bindPopup('<b>'+(f.properties.name||'Govt land')+'</b><br>'+(f.properties.agency||'')+' '+(f.properties.land_use||''))}).addTo(map);}
if(pts){const pc={GOVT_MCG:'#dc2626',GOVT_STATE:'#f97316',PRIVATE:'#782669'};L.geoJSON(pts,{pointToLayer:(f,ll)=>L.circleMarker(ll,{radius:8,color:'#fff',weight:1.5,fillColor:pc[f.properties.land_type]||'#782669',fillOpacity:.9}),onEachFeature:(f,l)=>l.on('click',()=>window.ReactNativeWebView.postMessage(JSON.stringify({type:'point',props:f.properties})))}).addTo(map);}
if(marker){L.circleMarker(marker,{radius:10,color:'#fff',weight:3,fillColor:'#782669',fillOpacity:1}).addTo(map);map.setView(marker,17);}
map.on('click',e=>window.ReactNativeWebView.postMessage(JSON.stringify({type:'map',lat:e.latlng.lat,lng:e.latlng.lng})));
map.locate({setView:!marker&&!pts,maxZoom:16});map.on('locationfound',e=>L.circle(e.latlng,{radius:e.accuracy/2,color:'#0d9488',weight:1}).addTo(map));
</script></body></html>`, [govtLand, points, marker, center, zoom]);
  return <WebView originWhitelist={["*"]} source={{ html }} style={{ flex: 1 }} geolocationEnabled onMessage={(e) => { try { const m = JSON.parse(e.nativeEvent.data); if (m.type === "point") onPointPress?.(m.props); if (m.type === "map") onMapPress?.(m.lat, m.lng); } catch { /* ignore */ } }} />;
}
