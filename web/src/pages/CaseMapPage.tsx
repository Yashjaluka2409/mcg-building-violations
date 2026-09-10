import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { dashboards, property } from "@/api/endpoints";
import MapView from "@/components/MapView";

/** Live enforcement map: case pins coloured by status (click = history), government-land parcels
 *  (click = cases on that parcel) and planned inspections. */
export default function CaseMapPage() {
  const nav = useNavigate();
  const [open, setOpen] = useState(true);
  const [showLand, setShowLand] = useState(true);
  const [showTasks, setShowTasks] = useState(true);
  const pts = useQuery({ queryKey: ["map-points", open, showTasks], queryFn: () => dashboards.map({ open: open ? 1 : 0, tasks: showTasks ? 1 : 0 }), refetchInterval: 60_000 });
  const land = useQuery({ queryKey: ["govt-land"], queryFn: () => property.govtLandGeoJson(), enabled: showLand });
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-3"><div><h1 className="page-title">Enforcement map</h1><p className="page-sub">Pins update with every action on a case - click a pin or a government-land parcel to see the case history</p></div><div className="flex-1" /><label className="text-sm flex items-center gap-1"><input type="checkbox" checked={open} onChange={(e) => setOpen(e.target.checked)} />Open cases only</label><label className="text-sm flex items-center gap-1"><input type="checkbox" checked={showLand} onChange={(e) => setShowLand(e.target.checked)} />Government land</label><label className="text-sm flex items-center gap-1"><input type="checkbox" checked={showTasks} onChange={(e) => setShowTasks(e.target.checked)} />Planned inspections</label></div>
      <MapView points={pts.data} govtLand={showLand ? land.data : undefined} fit legend height="calc(100vh - 200px)" onOpenCase={(id) => nav(`/cases/${id}`)} onOpenTask={() => nav("/tasks")} />
    </div>
  );
}
