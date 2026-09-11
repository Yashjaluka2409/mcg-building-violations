/**
 * Geotagged capture. Every photo/video is taken in-app; at the moment of capture we read a fresh
 * high-accuracy GPS fix and send it with the file, so the server can (a) store it, (b) compute the
 * distance from the case point and (c) refuse delivery/execution evidence taken elsewhere.
 * Gallery uploads are allowed only for documents (replies, sanction letters).
 *
 * Compression happens on the phone, before upload (the server hashes and signs what it receives):
 *  - photos are resized to at most PHOTO_MAX_EDGE px on the long edge and re-encoded as JPEG at
 *    PHOTO_QUALITY - roughly 300 KB instead of the 3-5 MB camera original, still legible on a notice;
 *  - videos are recorded at medium quality (iOS picker setting), capped at VIDEO_MAX_SECONDS and, in a
 *    native (EAS) build, re-encoded by react-native-compressor (~720p, WhatsApp-like size). Expo Go has
 *    no native compressor, so there only the picker's quality/duration settings apply.
 * Previews use the compressed photo / a video thumbnail so they appear immediately after capture.
 */
import * as FileSystem from "expo-file-system";
import * as ImageManipulator from "expo-image-manipulator";
import * as ImagePicker from "expo-image-picker";
import * as VideoThumbnails from "expo-video-thumbnails";
import { api, deviceId } from "@/api/client";
import { IntegritySignals, trustedFix } from "@/services/integrity";

export const PHOTO_MAX_EDGE = 1600;   // px on the long edge
export const PHOTO_QUALITY = 0.6;     // JPEG quality 0..1
export const DOC_MAX_EDGE = 2000;     // scanned documents keep a little more detail
export const DOC_QUALITY = 0.7;
export const VIDEO_MAX_SECONDS = 30;

/** A GPS fix plus the device-integrity signals collected with it (see services/integrity.ts). */
export interface Fix { latitude: number; longitude: number; accuracy: number | null; altitude: number | null; at: string; signals?: IntegritySignals; }
export interface Capture { uri: string; name: string; type: string; fix: Fix; thumbUri?: string; sizeBytes?: number; }

/** Fresh, anti-spoofing-checked fix. Throws IntegrityError when a mock provider / root / emulator is detected. */
export async function currentFix(): Promise<Fix> {
  return trustedFix();
}

async function fileSize(uri: string): Promise<number | undefined> {
  try { const info: any = await FileSystem.getInfoAsync(uri); return info?.exists ? info.size : undefined; } catch { return undefined; }
}

export function formatSize(bytes?: number): string {
  if (!bytes) return "";
  return bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

/** Downscale + re-encode a photo (EXIF is dropped; the geotag travels as form fields). Falls back to the original. */
export async function compressPhoto(uri: string, width?: number, height?: number, maxEdge = PHOTO_MAX_EDGE, quality = PHOTO_QUALITY): Promise<string> {
  try {
    const w = width || 0, h = height || 0;
    const actions = Math.max(w, h) > maxEdge ? [w >= h ? { resize: { width: maxEdge } } : { resize: { height: maxEdge } }] : [];
    const out = await ImageManipulator.manipulateAsync(uri, actions, { compress: quality, format: ImageManipulator.SaveFormat.JPEG });
    return out.uri;
  } catch { return uri; }
}

/** Re-encode a video with react-native-compressor when the native module is present (EAS build); no-op in Expo Go. */
export async function compressVideo(uri: string, onProgress?: (fraction: number) => void): Promise<string> {
  try {
    // eslint-disable-next-line @typescript-eslint/no-var-requires
    const mod = require("react-native-compressor");
    if (!mod?.Video?.compress) return uri;
    return await mod.Video.compress(uri, { compressionMethod: "auto", maxSize: 1280, progressDivider: 10 }, (p: number) => onProgress?.(p));
  } catch { return uri; }
}

export async function videoThumbnail(uri: string): Promise<string | undefined> {
  try { const r = await VideoThumbnails.getThumbnailAsync(uri, { time: 500, quality: 0.5 }); return r.uri; } catch { return undefined; }
}

export async function captureWithCamera(video = false, onStatus?: (msg: string) => void): Promise<Capture | null> {
  const perm = await ImagePicker.requestCameraPermissionsAsync();
  if (!perm.granted) throw new Error("Camera permission is required");
  const fixPromise = currentFix();                       // starts now, usually done before the shutter is pressed
  const res = await ImagePicker.launchCameraAsync({
    mediaTypes: video ? ["videos"] : ["images"], quality: 0.8, exif: false,
    videoMaxDuration: VIDEO_MAX_SECONDS, videoQuality: ImagePicker.UIImagePickerControllerQualityType.Medium,
  });
  if (res.canceled || !res.assets?.length) { fixPromise.catch(() => undefined); return null; }
  const a = res.assets[0];
  let uri = a.uri; let thumbUri: string | undefined;
  if (video) {
    onStatus?.("Compressing video…");
    uri = await compressVideo(a.uri, (p) => onStatus?.(`Compressing video… ${Math.round(p * 100)}%`));
    thumbUri = await videoThumbnail(uri);
  } else {
    onStatus?.("Compressing photo…");
    uri = await compressPhoto(a.uri, a.width, a.height);
    thumbUri = uri;
  }
  onStatus?.("Confirming location…");
  const fix = await fixPromise;
  const ext = video ? "mp4" : "jpg";
  return { uri, name: `capture-${Date.now()}.${ext}`, type: video ? "video/mp4" : "image/jpeg", fix, thumbUri, sizeBytes: await fileSize(uri) };
}

export async function pickDocument(): Promise<{ uri: string; name: string; type: string } | null> {
  const res = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], quality: 0.8 });
  if (res.canceled || !res.assets?.length) return null;
  const a = res.assets[0];
  const uri = await compressPhoto(a.uri, a.width, a.height, DOC_MAX_EDGE, DOC_QUALITY);
  return { uri, name: a.fileName || `doc-${Date.now()}.jpg`, type: "image/jpeg" };
}

export async function uploadMedia(file: { uri: string; name: string; type: string }, kind: string, opts: { caseId?: string; noticeId?: string; fix?: Fix | null; caption?: string; onProgress?: (fraction: number) => void }) {
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
  const r = await api.post("/media/", fd, { headers: { "Content-Type": "multipart/form-data" }, onUploadProgress: (e) => opts.onProgress?.(e.total ? e.loaded / e.total : 0) });
  return r.data;
}
