/**
 * Geotagged capture. Every photo/video is taken in-app; at the moment of capture we read a fresh
 * high-accuracy GPS fix and send it with the file, so the server can (a) store it, (b) compute the
 * distance from the case point and (c) refuse delivery/execution evidence taken elsewhere.
 * Gallery uploads are allowed only for documents (replies, sanction letters).
 */
import * as ImagePicker from "expo-image-picker";
import { api, deviceId } from "@/api/client";
import { IntegritySignals, trustedFix } from "@/services/integrity";

/** A GPS fix plus the device-integrity signals collected with it (see services/integrity.ts). */
export interface Fix { latitude: number; longitude: number; accuracy: number | null; altitude: number | null; at: string; signals?: IntegritySignals; }

/** Fresh, anti-spoofing-checked fix. Throws IntegrityError when a mock provider / root / emulator is detected. */
export async function currentFix(): Promise<Fix> {
  return trustedFix();
}

export async function captureWithCamera(video = false): Promise<{ uri: string; name: string; type: string; fix: Fix } | null> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) throw new Error("Camera permission is required");
  const fixPromise = currentFix();
  const res = await ImagePicker.launchCameraAsync({ mediaTypes: video ? ["videos"] : ["images"], quality: 0.7, videoMaxDuration: 60, exif: true });
  if (res.canceled || !res.assets?.length) return null;
  const a = res.assets[0];
  const fix = await fixPromise;
  const ext = video ? "mp4" : "jpg";
  return { uri: a.uri, name: a.fileName || `capture-${Date.now()}.${ext}`, type: video ? "video/mp4" : "image/jpeg", fix };
}

export async function pickDocument(): Promise<{ uri: string; name: string; type: string } | null> {
  const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.8 });
  if (res.canceled || !res.assets?.length) return null;
  const a = res.assets[0];
  return { uri: a.uri, name: a.fileName || `doc-${Date.now()}.jpg`, type: "image/jpeg" };
}

export async function uploadMedia(file: { uri: string; name: string; type: string }, kind: string, opts: { caseId?: string; noticeId?: string; fix?: Fix | null; caption?: string }) {
  const fd = new FormData();
  fd.append("file", { uri: file.uri, name: file.name, type: file.type } as any);
  fd.append("kind", kind);
  if (opts.caseId) fd.append("case", opts.caseId);
  if (opts.noticeId) fd.append("notice", opts.noticeId);
  if (opts.fix) {
    fd.append("latitude", opts.fix.latitude.toFixed(7)); fd.append("longitude", opts.fix.longitude.toFixed(7));
    if (opts.fix.accuracy != null) fd.append("accuracy_m", String(Math.round(opts.fix.accuracy)));
    if (opts.fix.altitude != null) fd.append("altitude_m", String(Math.round(opts.fix.altitude)));
    fd.append("captured_at", opts.fix.at);
    if (opts.fix.signals) fd.append("location_integrity", JSON.stringify(opts.fix.signals));   // anti-spoofing signals, judged by the server
  }
  fd.append("device_id", deviceId());
  if (opts.caption) fd.append("caption", opts.caption);
  const r = await api.post("/media/", fd, { headers: { "Content-Type": "multipart/form-data" } });
  return r.data;
}
