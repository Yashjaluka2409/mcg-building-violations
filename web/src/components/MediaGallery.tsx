import { IntegrityBadge } from "@/components/ui";
import { Camera, CheckCircle2, FileText, MapPin, Video, XCircle } from "lucide-react";
import type { Media } from "@/api/types";
import { fmtDateTime } from "@/utils/format";

export default function MediaGallery({ items, kind }: { items: Media[]; kind?: string }) {
  const list = kind ? items.filter((m) => m.kind === kind) : items;
  if (!list.length) return <div className="text-sm text-light-text-muted">No files.</div>;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {list.map((m) => (
        <a key={m.id} href={m.url || "#"} target="_blank" rel="noreferrer" className="card overflow-hidden group">
          <div className="aspect-video bg-gray-100 flex items-center justify-center overflow-hidden">
            {m.media_type === "IMAGE" && m.url ? <img src={m.url} alt={m.caption} className="w-full h-full object-cover group-hover:scale-105 transition-transform" /> : m.media_type === "VIDEO" ? <Video className="h-8 w-8 text-gray-400" /> : <FileText className="h-8 w-8 text-gray-400" />}
          </div>
          <div className="p-2 text-xs space-y-1">
            <div className="flex items-center justify-between"><span className="badge bg-primary-50 text-primary-700">{m.kind.replace(/_/g, " ")}</span>{m.latitude ? (m.geotag_verified ? <CheckCircle2 className="h-4 w-4 text-success-600" /> : <XCircle className="h-4 w-4 text-danger-500" />) : <Camera className="h-4 w-4 text-gray-300" />}</div>
            {m.latitude && <div><IntegrityBadge status={m.integrity_status} reasons={m.integrity_reasons} compact /></div>}
            {m.latitude && <div className="flex items-center gap-1 text-light-text-muted"><MapPin className="h-3 w-3" />{Number(m.latitude).toFixed(5)}, {Number(m.longitude).toFixed(5)}{m.distance_from_case_m != null && <span> · {Number(m.distance_from_case_m).toFixed(0)} m</span>}</div>}
            <div className="text-light-text-muted">{fmtDateTime(m.captured_at || m.created_at)}{m.uploaded_by ? ` · ${m.uploaded_by.name}` : ""}</div>
            {m.caption && <div className="truncate">{m.caption}</div>}
          </div>
        </a>
      ))}
    </div>
  );
}
