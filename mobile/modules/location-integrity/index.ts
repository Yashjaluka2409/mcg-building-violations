/**
 * Local Expo module "LocationIntegrity" — native anti-GPS-spoofing signals + hardware attestation.
 *
 * Android (Kotlin): Developer options, legacy mock-location setting, installed mock-location apps, VPN transport,
 * system proxy, root heuristics, emulator heuristics, whether the last fix was mocked, Play Integrity token.
 * iOS (Swift): jailbreak heuristics, simulator, VPN / proxy from the system proxy settings, CoreLocation
 * `sourceInformation` (isSimulatedBySoftware / isProducedByAccessory, iOS 15+), App Attest key + assertion.
 *
 * The module only exists in a development / EAS build. In Expo Go `LocationIntegrity` is null and the app falls
 * back to the JavaScript-only signals (expo-location `mocked`, expo-device root check, expo-network VPN type);
 * the server records that the native checks were unavailable and, in production, refuses such captures
 * (setting "require_native_integrity_module").
 */
import { requireOptionalNativeModule } from "expo-modules-core";

export interface NativeDeviceSignals {
  native_module: true;
  developer_options?: boolean | null;
  mock_location_setting?: boolean | null;
  mock_apps_installed?: string[];
  vpn_active?: boolean | null;
  proxy_configured?: boolean | null;
  rooted?: boolean | null;
  is_physical_device?: boolean | null;
  last_fix_mocked?: boolean | null;
}

export interface NativeSourceInfo {
  latitude?: number; longitude?: number; accuracy?: number; timestamp?: number;
  simulated_by_software?: boolean; produced_by_accessory?: boolean;
}

export interface Attestation {
  type: "play_integrity" | "app_attest";
  nonce: string;
  token?: string;        // Play Integrity
  key_id?: string;       // App Attest
  attestation?: string;  // App Attest first use (base64 CBOR)
  assertion?: string;    // App Attest subsequent captures (base64 CBOR)
}

interface NativeModule {
  getDeviceSignals(): NativeDeviceSignals;
  /** iOS only: one fresh CoreLocation fix with its source information. */
  getLocationSourceInfo?(): Promise<NativeSourceInfo | null>;
  /** Android: (nonce, cloudProjectNumber). iOS: (nonce, existingKeyId | null). Resolves null when unsupported. */
  requestAttestation?(nonce: string, arg: string | null): Promise<Attestation | null>;
}

export const LocationIntegrity = requireOptionalNativeModule<NativeModule>("LocationIntegrity");
export const hasNativeIntegrity = LocationIntegrity != null;
