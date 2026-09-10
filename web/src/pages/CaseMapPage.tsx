import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { dashboards, property } from "@/api/endpoints";
import MapView from "@/components/MapView";

export default function CaseMapPage() {
  const nav = useNavigate();
  const [open, setOpen] = useState(true);
  const [showLand, setShowLand] = useState(true);
  const pts = useQuery({ queryKey: ["map-points", open], queryFn: () => dashboards.map({ open: open ? 1 : 0 }) });
  const land = useQuery({ queryKey: ["govt-land"], queryFn: () => property.govtLandGeoJson(), enabled: showLand });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3"><div><h1 className="page-title">Case map</h1><p className="page-sub">Red = MCG land, orange = other government land, purple = private land</p></div><div className="flex-1" /><label className="text-sm flex items-center gap-1"><input type="checkbox" checked={open} onChange={(e) => setOpen(e.target.checked)} />Open cases only</label><label className="text-sm flex items-center gap-1"><input type="checkbox" checked={showLand} onChange={(e) => setShowLand(e.target.checked)} />Government land layer</label></div>
      <MapView points={pts.data} govtLand={showLand ? land.data : undefined} fit height="calc(100vh - 200px)" onPointClick={(p) => nav(`/cases/${p.id}`)} />
    </div>
  );
}
