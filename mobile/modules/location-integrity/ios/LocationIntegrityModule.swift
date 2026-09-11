import ExpoModulesCore
import CoreLocation
import CryptoKit
import DeviceCheck
import Foundation
import UIKit

/// Native anti-GPS-spoofing signals for iOS (see modules/location-integrity/index.ts).
/// iOS has no "mock location" provider: spoofing needs a jailbreak or a computer-tethered simulation, which
/// CoreLocation reports through `CLLocationSourceInformation.isSimulatedBySoftware` (iOS 15+).
public class LocationIntegrityModule: Module {
  private let locator = OneShotLocator()

  public func definition() -> ModuleDefinition {
    Name("LocationIntegrity")

    Function("getDeviceSignals") { () -> [String: Any?] in
      return [
        "native_module": true,
        "rooted": Self.isJailbroken(),
        "is_physical_device": Self.isPhysicalDevice(),
        "vpn_active": Self.vpnActive(),
        "proxy_configured": Self.proxyConfigured(),
        "developer_options": nil,
        "mock_location_setting": nil,
      ]
    }

    // One fresh fix with its source information (simulated by software / produced by accessory).
    AsyncFunction("getLocationSourceInfo") { (promise: Promise) in
      self.locator.request { location, error in
        if let error = error { promise.reject("E_LOCATION", error.localizedDescription); return }
        var out: [String: Any?] = [
          "latitude": location?.coordinate.latitude,
          "longitude": location?.coordinate.longitude,
          "accuracy": location?.horizontalAccuracy,
          "timestamp": location.map { $0.timestamp.timeIntervalSince1970 * 1000 },
        ]
        if #available(iOS 15.0, *), let info = location?.sourceInformation {
          out["simulated_by_software"] = info.isSimulatedBySoftware
          out["produced_by_accessory"] = info.isProducedByAccessory
        }
        promise.resolve(out)
      }
    }

    // Apple App Attest: first call (no key id) creates + attests a Secure Enclave key; later calls sign an
    // assertion over sha256(nonce) with that key. Resolves nil when App Attest is unsupported (simulator).
    AsyncFunction("requestAttestation") { (nonce: String, existingKeyId: String?, promise: Promise) in
      guard #available(iOS 14.0, *), DCAppAttestService.shared.isSupported else { promise.resolve(nil); return }
      let service = DCAppAttestService.shared
      let clientHash = Data(SHA256.hash(data: Data(nonce.utf8)))
      if let keyId = existingKeyId, !keyId.isEmpty {
        service.generateAssertion(keyId, clientDataHash: clientHash) { assertion, error in
          if let error = error { promise.reject("E_ASSERTION", error.localizedDescription); return }
          promise.resolve(["type": "app_attest", "key_id": keyId, "assertion": assertion?.base64EncodedString() ?? "", "nonce": nonce])
        }
      } else {
        service.generateKey { keyId, error in
          guard let keyId = keyId, error == nil else { promise.reject("E_KEY", error?.localizedDescription ?? "generateKey failed"); return }
          service.attestKey(keyId, clientDataHash: clientHash) { attestation, error in
            if let error = error { promise.reject("E_ATTEST", error.localizedDescription); return }
            promise.resolve(["type": "app_attest", "key_id": keyId, "attestation": attestation?.base64EncodedString() ?? "", "nonce": nonce])
          }
        }
      }
    }
  }

  // ---- signals ----------------------------------------------------------------------------------------
  static func isPhysicalDevice() -> Bool {
    #if targetEnvironment(simulator)
      return false
    #else
      return true
    #endif
  }

  static func isJailbroken() -> Bool {
    #if targetEnvironment(simulator)
      return false
    #else
      let paths = ["/Applications/Cydia.app", "/Applications/Sileo.app", "/Library/MobileSubstrate/MobileSubstrate.dylib", "/bin/bash", "/usr/sbin/sshd",
                   "/etc/apt", "/private/var/lib/apt/", "/usr/bin/ssh", "/var/jb", "/Applications/FakeLocation.app", "/Library/MobileSubstrate/DynamicLibraries/LocationFaker.dylib"]
      for p in paths where FileManager.default.fileExists(atPath: p) { return true }
      if let url = URL(string: "cydia://package/com.example.package"), UIApplication.shared.canOpenURL(url) { return true }
      let probe = "/private/bvms_jb_probe_\(UUID().uuidString)"
      do { try "x".write(toFile: probe, atomically: true, encoding: .utf8); try? FileManager.default.removeItem(atPath: probe); return true } catch { return false }
    #endif
  }

  /// VPN: the system proxy settings expose the scoped interfaces; utun/tap/tun/ppp/ipsec mean a VPN tunnel is up.
  static func vpnActive() -> Bool {
    guard let settings = CFNetworkCopySystemProxySettings()?.takeRetainedValue() as? [String: Any],
          let scoped = settings["__SCOPED__"] as? [String: Any] else { return false }
    let vpnPrefixes = ["tap", "tun", "ppp", "ipsec", "utun"]
    return scoped.keys.contains { key in vpnPrefixes.contains { key.hasPrefix($0) } }
  }

  static func proxyConfigured() -> Bool {
    guard let settings = CFNetworkCopySystemProxySettings()?.takeRetainedValue() as? [String: Any] else { return false }
    let http = (settings["HTTPEnable"] as? Int ?? 0) == 1
    let https = (settings["HTTPSEnable"] as? Int ?? 0) == 1
    let pac = (settings["ProxyAutoConfigEnable"] as? Int ?? 0) == 1
    return http || https || pac
  }
}

final class OneShotLocator: NSObject, CLLocationManagerDelegate {
  private let manager = CLLocationManager()
  private var completion: ((CLLocation?, Error?) -> Void)?

  func request(_ done: @escaping (CLLocation?, Error?) -> Void) {
    DispatchQueue.main.async {
      self.completion = done
      self.manager.delegate = self
      self.manager.desiredAccuracy = kCLLocationAccuracyBest
      if self.manager.authorizationStatus == .notDetermined { self.manager.requestWhenInUseAuthorization() }
      self.manager.requestLocation()
    }
  }

  func locationManager(_ manager: CLLocationManager, didUpdateLocations locations: [CLLocation]) {
    completion?(locations.last, nil); completion = nil
  }

  func locationManager(_ manager: CLLocationManager, didFailWithError error: Error) {
    completion?(nil, error); completion = nil
  }
}
