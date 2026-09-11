/**
 * Location integrity (anti-GPS-spoofing) on the device.
 *
 * `trustedFix()` replaces a plain GPS read everywhere the app records a location as evidence. It takes two fresh
 * fixes, collects the device-integrity signals (mock provider, root/jailbreak, emulator, Developer options,
 * VPN / proxy, iOS software-simulated location, fix age, jitter), optionally obtains a hardware attestation
 * (Play Integrity / App Attest) bound to a server nonce, and refuses on the spot when spoofing is unambiguous.
 * The full signal set travels with the upload as `location_integrity`, and the server makes the final,
 * admin-configurable decision (services/location_integrity.py). Nothing here is trusted on its own.
 *
 * In Expo Go the native module is absent: only the JavaScript signals are available and `native_module` is
 * false, which the server records (and, in production, refuses).
 */
import * as Application from "expo-application";
import Constants from "expo-constants";
import * as Device from "expo-device";
import * as Location from "expo-location";
import * as Network from "expo-network";
import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import { api, deviceId } from "@/api/client";
import { Attestation, LocationIntegrity, hasNativeIntegrity } from "../../modules/location-integrity";

export interface IntegritySignals {
  source: "app";
  platform: string;
  native_module: boolean;
  app_version: string | null;
  build_number: string | null;
  os_version: string | null;
  device_model: string | null;
  device_id: string;
  is_physical_device: boolean | null;
  rooted: boolean | null;
  developer_options: boolean | null;
  mock_location: boolean | null;
  mock_apps_installed?: string[];
  vpn_active: boolean | null;
  proxy_configured: boolean | null;
  simulated_by_software: boolean | null;
  produced_by_accessory: boolean | null;
  provider: string;
  speed_mps: number | null;
  heading: number | null;
  fix_at: string;
  fix_age_s: number;
  jitter_m: number | null;
  attestation: Attestation | null;
}

export interface TrustedFix {
  latitude: number; longitude: number; accuracy: number | null; altitude: number | null; at: string;
  signals: IntegritySignals;
}

export class IntegrityError extends Error {
  codes: string[];
  constructor(codes: string[]) {
    super(`Location integrity check failed: ${codes.map((c) => TEXT[c] || c).join("; ")}. ${ADVICE}`);
    this.codes = codes;
  }
}

export const TEXT: Record<string, string> = {
  MOCK_LOCATION: "a mock (fake) GPS app such as FlyGPS or Fake GPS Location is providing the location",
  SIMULATED_LOCATION: "the location is being simulated by software (computer-tethered spoofing)",
  ROOTED_DEVICE: "this phone is rooted / jailbroken",
  EMULATOR: "the app is running on an emulator / simulator",
  DEVELOPER_OPTIONS: "Android Developer options are enabled",
  VPN_ACTIVE: "a VPN is active",
  PROXY_CONFIGURED: "a system proxy is configured",
  NATIVE_CHECKS_UNAVAILABLE: "this build (Expo Go) cannot run the native anti-spoofing checks",
  NO_NATIVE_INTEGRITY: "this build (Expo Go) cannot run the native anti-spoofing checks",
  STALE_FIX: "the GPS fix is too old",
  POOR_ACCURACY: "the GPS accuracy is too wide",
  IMPLAUSIBLE_TRAVEL: "your previous location implies impossible travel speed",
  IP_VPN_OR_PROXY: "the network address belongs to a VPN / proxy",
  ATTESTATION_MISSING: "device attestation is missing",
  ATTESTATION_FAILED: "device attestation failed",
  WEB_UNVERIFIED: "browser locations cannot be verified",
};
export const ADVICE = "Evidence with a spoofed or untrusted location is not accepted. Disable mock-location apps, VPN / proxy and Developer options, then try again.";

/** Signals that are unambiguous spoofing: refused on the device before anything is sent. */
const CLIENT_BLOCK: Array<[keyof IntegritySignals, unknown, string]> = [
  ["mock_location", true, "MOCK_LOCATION"], ["simulated_by_software", true, "SIMULATED_LOCATION"],
  ["rooted", true, "ROOTED_DEVICE"], ["is_physical_device", false, "EMULATOR"],
];

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));
const R = 6371000;
export function haversineM(a: { latitude: number; longitude: number }, b: { latitude: number; longitude: number }) {
  const t = (d: number) => (d * Math.PI) / 180;
  const dLat = t(b.latitude - a.latitude), dLng = t(b.longitude - a.longitude);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(t(a.latitude)) * Math.cos(t(b.latitude)) * Math.sin(dLng / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

/** Device-level signals that do not need a GPS fix (used by the home-screen pre-check and every capture). */
export async function deviceSignals(): Promise<Omit<IntegritySignals, "provider" | "speed_mps" | "heading" | "fix_at" | "fix_age_s" | "jitter_m" | "mock_location" | "attestation" | "simulated_by_software" | "produced_by_accessory">> {
  let native: Record<string, any> = {};
  try { native = LocationIntegrity?.getDeviceSignals?.() ?? {}; } catch { native = {}; }
  const [rootedJs, net] = await Promise.all([
    Device.isRootedExperimentalAsync().catch(() => null),
    Network.getNetworkStateAsync().catch(() => null),
  ]);
  const vpnJs = net?.type === Network.NetworkStateType.VPN ? true : null;
  return {
    source: "app",
    platform: Platform.OS,
    native_module: hasNativeIntegrity,
    app_version: Application.nativeApplicationVersion ?? Constants.expoConfig?.version ?? null,
    build_number: Application.nativeBuildVersion ?? null,
    os_version: Device.osVersion ?? null,
    device_model: Device.modelName ?? null,
    device_id: deviceId(),
    is_physical_device: native.is_physical_device ?? Device.isDevice ?? null,
    rooted: native.rooted === true || rootedJs === true ? true : (native.rooted ?? rootedJs ?? null),
    developer_options: native.developer_options ?? null,
    mock_apps_installed: Array.isArray(native.mock_apps_installed) ? native.mock_apps_installed : undefined,
    vpn_active: native.vpn_active === true || vpnJs === true ? true : (native.vpn_active ?? vpnJs ?? null),
    proxy_configured: native.proxy_configured ?? null,
  };
}

async function attestation(): Promise<Attestation | null> {
  if (!LocationIntegrity?.requestAttestation) return null;
  try {
    const { nonce } = (await api.post("/integrity/nonce/")).data as { nonce: string };
    if (Platform.OS === "android") {
      const project = String((Constants.expoConfig?.extra as any)?.playIntegrityCloudProjectNumber || "");
      return await LocationIntegrity.requestAttestation(nonce, project || null);
    }
    const keyId = await SecureStore.getItemAsync("appAttestKeyId");
    const res = await LocationIntegrity.requestAttestation(nonce, keyId);
    if (res?.key_id && res.attestation) await SecureStore.setItemAsync("appAttestKeyId", res.key_id);
    return res;
  } catch {
    return null; // the server decides whether attestation is mandatory
  }
}

/** A fresh, trusted GPS fix with its integrity signals. Throws IntegrityError when spoofing is unambiguous. */
export async function trustedFix(opts: { withAttestation?: boolean; accuracy?: Location.Accuracy } = {}): Promise<TrustedFix> {
  const { status } = await Location.requestForegroundPermissionsAsync();
  if (status !== "granted") throw new Error("Location permission is required to record evidence");
  const accuracy = opts.accuracy ?? Location.Accuracy.Highest;
  const p1 = await Location.getCurrentPositionAsync({ accuracy, mayShowUserSettingsDialog: true });
  await sleep(1200);
  const p2 = await Location.getCurrentPositionAsync({ accuracy }).catch(() => p1);
  const [base, source, att] = await Promise.all([
    deviceSignals(),
    LocationIntegrity?.getLocationSourceInfo ? LocationIntegrity.getLocationSourceInfo().catch(() => null) : Promise.resolve(null),
    opts.withAttestation === false ? Promise.resolve(null) : attestation(),
  ]);
  const p = p2.timestamp >= p1.timestamp ? p2 : p1;
  const mocked = (p as any).mocked ?? (p1 as any).mocked ?? null; // Android: Location.isMock / isFromMockProvider
  const signals: IntegritySignals = {
    ...base,
    mock_location: mocked === true || (base.mock_apps_installed?.length ? mocked : mocked) === true ? true : (mocked ?? null),
    simulated_by_software: source?.simulated_by_software ?? null,
    produced_by_accessory: source?.produced_by_accessory ?? null,
    provider: Platform.OS === "ios" ? "corelocation" : "fused",
    speed_mps: p.coords.speed ?? null,
    heading: p.coords.heading ?? null,
    fix_at: new Date(p.timestamp).toISOString(),
    fix_age_s: Math.max(0, (Date.now() - p.timestamp) / 1000),
    jitter_m: Math.round(haversineM(p1.coords, p2.coords) * 100) / 100,
    attestation: att,
  };
  const blocked = CLIENT_BLOCK.filter(([k, v]) => (signals as any)[k] === v).map(([, , code]) => code);
  if (blocked.length) throw new IntegrityError(blocked);
  return { latitude: p.coords.latitude, longitude: p.coords.longitude, accuracy: p.coords.accuracy ?? null, altitude: p.coords.altitude ?? null, at: signals.fix_at, signals };
}

export interface PrecheckResult { decision: "PASS" | "FLAGGED" | "REJECTED"; reasons: string[]; flags: string[]; explanation: string; advice: string; native_module: boolean; }

/** Home-screen pre-check: asks the server for the verdict on this device right now (never throws). */
export async function precheck(): Promise<PrecheckResult> {
  let fix: TrustedFix | null = null;
  let clientCodes: string[] = [];
  try { fix = await trustedFix({ withAttestation: false, accuracy: Location.Accuracy.High }); }
  catch (e) { if (e instanceof IntegrityError) clientCodes = e.codes; }
  try {
    const signals = fix?.signals ?? { ...(await deviceSignals()), mock_location: clientCodes.includes("MOCK_LOCATION") ? true : null,
      simulated_by_software: clientCodes.includes("SIMULATED_LOCATION") ? true : null, native_module: hasNativeIntegrity };
    const r = await api.post("/integrity/precheck/", { latitude: fix?.latitude, longitude: fix?.longitude, accuracy_m: fix?.accuracy, device_id: deviceId(), location_integrity: signals });
    return r.data as PrecheckResult;
  } catch {
    return clientCodes.length
      ? { decision: "REJECTED", reasons: clientCodes, flags: [], explanation: clientCodes.map((c) => TEXT[c] || c).join("; "), advice: ADVICE, native_module: hasNativeIntegrity }
      : { decision: "FLAGGED", reasons: [], flags: ["OFFLINE"], explanation: "Could not reach the server to verify this device", advice: "", native_module: hasNativeIntegrity };
  }
}
