package gov.mcg.bvms.integrity

import android.content.Context
import android.content.pm.PackageManager
import android.location.LocationManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import android.provider.Settings
import com.google.android.play.core.integrity.IntegrityManagerFactory
import com.google.android.play.core.integrity.StandardIntegrityManager
import com.google.android.play.core.integrity.StandardIntegrityManager.PrepareIntegrityTokenRequest
import com.google.android.play.core.integrity.StandardIntegrityManager.StandardIntegrityTokenRequest
import expo.modules.kotlin.Promise
import expo.modules.kotlin.modules.Module
import expo.modules.kotlin.modules.ModuleDefinition
import java.io.File
import java.security.MessageDigest

/**
 * Native anti-GPS-spoofing signals for the MCG Building Violations app (see modules/location-integrity/index.ts).
 * Everything here is a *signal*; the server (services/location_integrity.py) decides what blocks.
 */
class LocationIntegrityModule : Module() {
  private val context: Context
    get() = requireNotNull(appContext.reactContext) { "React context is not available" }

  private var tokenProvider: StandardIntegrityManager.StandardIntegrityTokenProvider? = null

  override fun definition() = ModuleDefinition {
    Name("LocationIntegrity")

    Function("getDeviceSignals") {
      mapOf(
        "native_module" to true,
        "developer_options" to developerOptionsEnabled(),
        "mock_location_setting" to legacyMockLocationSetting(),
        "mock_apps_installed" to mockLocationApps(),
        "vpn_active" to vpnActive(),
        "proxy_configured" to proxyConfigured(),
        "rooted" to looksRooted(),
        "is_physical_device" to !looksEmulator(),
        "last_fix_mocked" to lastFixMocked(),
      )
    }

    // Google Play Integrity standard request bound to sha256(nonce) as the request hash.
    AsyncFunction("requestAttestation") { nonce: String, cloudProjectNumber: String?, promise: Promise ->
      try {
        if (cloudProjectNumber.isNullOrBlank()) { promise.resolve(null); return@AsyncFunction }
        val manager = IntegrityManagerFactory.createStandard(context)
        val requestHash = sha256Hex(nonce)
        val issue: (StandardIntegrityManager.StandardIntegrityTokenProvider) -> Unit = { provider ->
          provider.request(StandardIntegrityTokenRequest.builder().setRequestHash(requestHash).build())
            .addOnSuccessListener { promise.resolve(mapOf("type" to "play_integrity", "token" to it.token(), "nonce" to nonce)) }
            .addOnFailureListener { promise.reject("E_INTEGRITY", it.message ?: "integrity request failed", it) }
        }
        val cached = tokenProvider
        if (cached != null) {
          issue(cached)
        } else {
          manager.prepareIntegrityToken(PrepareIntegrityTokenRequest.builder().setCloudProjectNumber(cloudProjectNumber.toLong()).build())
            .addOnSuccessListener { tokenProvider = it; issue(it) }
            .addOnFailureListener { promise.reject("E_INTEGRITY_PREPARE", it.message ?: "integrity prepare failed", it) }
        }
      } catch (e: Throwable) {
        promise.reject("E_INTEGRITY", e.message ?: "integrity error", e)
      }
    }
  }

  // ---- signals -------------------------------------------------------------------------------------------
  private fun developerOptionsEnabled(): Boolean = try {
    Settings.Global.getInt(context.contentResolver, Settings.Global.DEVELOPMENT_SETTINGS_ENABLED, 0) == 1
  } catch (e: Throwable) { false }

  @Suppress("DEPRECATION")
  private fun legacyMockLocationSetting(): Boolean? = try {
    if (Build.VERSION.SDK_INT < Build.VERSION_CODES.M)
      Settings.Secure.getString(context.contentResolver, Settings.Secure.ALLOW_MOCK_LOCATION) != "0"
    else null   // per-app mock selection since Android 6; detected per fix (isMock) and via installed apps
  } catch (e: Throwable) { null }

  private fun mockLocationApps(): List<String> = try {
    val pm = context.packageManager
    val self = context.packageName
    pm.getInstalledPackages(PackageManager.GET_PERMISSIONS)
      .filter { it.packageName != self && it.requestedPermissions?.contains("android.permission.ACCESS_MOCK_LOCATION") == true }
      .map { it.packageName }
  } catch (e: Throwable) { emptyList() }

  private fun vpnActive(): Boolean = try {
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val nets = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) listOfNotNull(cm.activeNetwork) + cm.allNetworks.toList() else cm.allNetworks.toList()
    nets.any { n -> cm.getNetworkCapabilities(n)?.hasTransport(NetworkCapabilities.TRANSPORT_VPN) == true }
  } catch (e: Throwable) { false }

  private fun proxyConfigured(): Boolean = try {
    val host = System.getProperty("http.proxyHost")
    val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
    val sys = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) cm.defaultProxy else null
    (!host.isNullOrBlank()) || (sys != null && !sys.host.isNullOrBlank())
  } catch (e: Throwable) { false }

  private fun looksRooted(): Boolean {
    val paths = listOf("/system/app/Superuser.apk", "/sbin/su", "/system/bin/su", "/system/xbin/su", "/data/local/xbin/su", "/data/local/bin/su",
      "/system/sd/xbin/su", "/system/bin/failsafe/su", "/data/local/su", "/su/bin/su", "/sbin/.magisk", "/data/adb/magisk", "/system/xbin/daemonsu")
    if (paths.any { File(it).exists() }) return true
    if (Build.TAGS?.contains("test-keys") == true) return true
    return try {
      val p = Runtime.getRuntime().exec(arrayOf("/system/xbin/which", "su"))
      p.inputStream.bufferedReader().readLine() != null
    } catch (e: Throwable) { false }
  }

  private fun looksEmulator(): Boolean {
    val fp = Build.FINGERPRINT ?: ""; val model = Build.MODEL ?: ""; val product = Build.PRODUCT ?: ""
    val hw = Build.HARDWARE ?: ""; val brand = Build.BRAND ?: ""; val device = Build.DEVICE ?: ""; val manuf = Build.MANUFACTURER ?: ""
    return fp.startsWith("generic") || fp.startsWith("unknown") || fp.contains("emulator") ||
      model.contains("google_sdk") || model.contains("Emulator") || model.contains("Android SDK built for") ||
      manuf.contains("Genymotion") || hw.contains("goldfish") || hw.contains("ranchu") || hw.contains("vbox") ||
      product.contains("sdk") || product.contains("emulator") || product.contains("simulator") ||
      (brand.startsWith("generic") && device.startsWith("generic"))
  }

  @Suppress("DEPRECATION", "MissingPermission")
  private fun lastFixMocked(): Boolean? = try {
    val lm = context.getSystemService(Context.LOCATION_SERVICE) as LocationManager
    val loc = lm.getLastKnownLocation(LocationManager.GPS_PROVIDER) ?: lm.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
    when {
      loc == null -> null
      Build.VERSION.SDK_INT >= Build.VERSION_CODES.S -> loc.isMock
      else -> loc.isFromMockProvider
    }
  } catch (e: Throwable) { null }

  private fun sha256Hex(s: String): String =
    MessageDigest.getInstance("SHA-256").digest(s.toByteArray()).joinToString("") { "%02x".format(it) }
}
