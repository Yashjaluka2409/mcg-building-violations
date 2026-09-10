import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload } from "lucide-react";
import { useState } from "react";
import { property } from "@/api/endpoints";
import { errorMessage } from "@/api/client";
import MapView from "@/components/MapView";
import { Alert, Card, Field } from "@/components/ui";
import { useAuth } from "@/store/auth";

const AGENCIES = ["MCG", "HSVP", "GMDA", "STATE_GOVT", "PWD", "IRRIGATION", "FOREST", "PANCHAYAT", "RAILWAYS", "NHAI", "DEFENCE", "OTHER"];

export default function GovtLandPage() {
  const qc = useQueryClient();
  const user = useAuth((s) => s.user);
  const [f, setF] = useState<{ name: string; agency: string; remarks: string; file: File | null }>({ name: "", agency: "MCG", remarks: "", file: null });
  const [msg, setMsg] = useState("");
  const land = useQuery({ queryKey: ["govt-land"], queryFn: () => property.govtLandGeoJson() });
  const up = useMutation({ mutationFn: () => { const fd = new FormData(); fd.append("name", f.name); fd.append("agency", f.agency); fd.append("remarks", f.remarks); fd.append("source_file", f.file!); return property.uploadLandLayer(fd); }, onSuccess: (r) => { setMsg(`Layer "${r.name}" loaded: ${r.feature_count} parcels`); qc.invalidateQueries({ queryKey: ["govt-land"] }); }, onError: (e) => setMsg(errorMessage(e)) });
  const isAdmin = ["ADMIN", "COMMISSIONER", "ADDL_COMMISSIONER"].includes(user?.role || "");
  const counts: Record<string, number> = {};
  for (const ft of land.data?.features || []) counts[ft.properties.agency] = (counts[ft.properties.agency] || 0) + 1;
  return (
    <div className="space-y-4">
      <div><h1 className="page-title">Government land layers</h1><p className="page-sub">Parcels of MCG / HSVP / GMDA / State land used by the app to flag constructions on government land automatically. Upload GeoJSON exported from QGIS (EPSG:4326).</p></div>
      <div className="grid lg:grid-cols-3 gap-4">
        <Card title="Map" className="lg:col-span-2"><MapView govtLand={land.data} fit height="560px" /><div className="flex flex-wrap gap-2 mt-2 text-xs">{Object.entries(counts).map(([a, n]) => <span key={a} className="badge bg-gray-100">{a}: {n}</span>)}</div></Card>
        <div className="space-y-4">
          {isAdmin && <Card title="Upload layer (GeoJSON)"><div className="space-y-2"><Field label="Layer name"><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. MCG green belts - Zone 2" /></Field><Field label="Owning agency"><select className="input" value={f.agency} onChange={(e) => setF({ ...f, agency: e.target.value })}>{AGENCIES.map((a) => <option key={a}>{a}</option>)}</select></Field><Field label="Remarks / source"><input className="input" value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} placeholder="Revenue record / survey / drone" /></Field><input type="file" accept=".geojson,.json" className="input" onChange={(e) => setF({ ...f, file: e.target.files?.[0] || null })} /><button className="btn-primary w-full" disabled={!f.file || !f.name || up.isPending} onClick={() => up.mutate()}><Upload className="h-4 w-4" />Upload</button>{msg && <Alert kind="info">{msg}</Alert>}</div></Card>}
          <Card title="How the check works"><ol className="text-sm list-decimal ml-4 space-y-1"><li>Every inspection point (and every geotagged photo) is tested against these polygons.</li><li>If it falls inside a parcel the case is flagged <b>Government land</b> and the GL-xx violations / s.408A route become available.</li><li>Feature properties <code>name, land_use, village, khasra, area_sqm</code> are read if present.</li><li>Convert shapefiles in QGIS: Layer → Export → Save Features As → GeoJSON, CRS EPSG:4326.</li></ol></Card>
        </div>
      </div>
    </div>
  );
}
