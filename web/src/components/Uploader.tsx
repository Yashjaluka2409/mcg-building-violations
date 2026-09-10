import { Camera, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { media as mediaApi } from "@/api/endpoints";
import type { Media } from "@/api/types";
import { errorMessage } from "@/api/client";

/** Web uploader: captures the browser's GPS fix at the moment of selection so that desk-uploaded
 *  photos also carry a location (the mobile app does this from the camera). */
export default function Uploader({ caseId, kind, noticeId, onUploaded, accept = "image/*,video/*,.pdf", label = "Upload photos / videos / documents", requireGeo }: { caseId?: string; kind: string; noticeId?: string; onUploaded: (m: Media) => void; accept?: string; label?: string; requireGeo?: boolean }) {
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [err, setErr] = useState("");

  const geo = () => new Promise<GeolocationPosition | null>((res) => { if (!navigator.geolocation) return res(null); navigator.geolocation.getCurrentPosition((p) => res(p), () => res(null), { enableHighAccuracy: true, timeout: 8000 }); });

  const onFiles = async (files: FileList | null) => {
    if (!files?.length) return;
    setBusy(true); setErr("");
    const pos = await geo();
    if (requireGeo && !pos) { setErr("Location is required for this upload - allow location access in the browser or use the mobile app."); setBusy(false); return; }
    try {
      for (const f of Array.from(files)) {
        const fd = new FormData();
        fd.append("file", f); fd.append("kind", kind);
        if (caseId) fd.append("case", caseId);
        if (noticeId) fd.append("notice", noticeId);
        if (pos) { fd.append("latitude", pos.coords.latitude.toFixed(7)); fd.append("longitude", pos.coords.longitude.toFixed(7)); fd.append("accuracy_m", String(Math.round(pos.coords.accuracy))); }
        fd.append("captured_at", new Date(f.lastModified || Date.now()).toISOString());
        onUploaded(await mediaApi.upload(fd, setProgress));
      }
    } catch (e) { setErr(errorMessage(e)); }
    setBusy(false); setProgress(0);
    if (input.current) input.current.value = "";
  };
  return (
    <div>
      <button type="button" className="btn-outline w-full border-dashed py-4 justify-center" disabled={busy} onClick={() => input.current?.click()}>
        {busy ? <><Upload className="h-4 w-4 animate-pulse" /> Uploading {progress}%</> : <><Camera className="h-4 w-4 text-accent-600" /> {label}</>}
      </button>
      <input ref={input} type="file" multiple accept={accept} capture={requireGeo ? "environment" : undefined} className="hidden" onChange={(e) => onFiles(e.target.files)} />
      {err && <div className="text-xs text-danger-600 mt-1">{err}</div>}
    </div>
  );
}
