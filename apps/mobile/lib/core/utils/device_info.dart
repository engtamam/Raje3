import 'dart:io';
import 'package:device_info_plus/device_info_plus.dart';
import 'package:package_info_plus/package_info_plus.dart';

/// Helper class for collecting device and app information.
///
/// Used for:
/// - Including device info in API requests (for analytics and debugging)
/// - Displaying app version in settings screens
/// - Platform-specific behavior
///
/// Usage:
/// ```dart
/// final info = await DeviceInfoHelper.getDeviceInfo();
/// // {
/// //   'platform': 'android',
/// //   'model': 'Samsung Galaxy S24',
/// //   'os_version': '14',
/// //   'app_version': '1.0.0',
/// //   'build_number': '1',
/// //   'device_id': 'xxxx...',
/// // }
/// ```
class DeviceInfoHelper {
  DeviceInfoHelper._(); // Prevent instantiation

  static final DeviceInfoPlugin _deviceInfoPlugin = DeviceInfoPlugin();

  /// Cached device info to avoid repeated platform calls.
  static Map<String, String>? _cachedInfo;

  /// Get comprehensive device and app information.
  ///
  /// Results are cached after the first call for performance.
  static Future<Map<String, String>> getDeviceInfo() async {
    if (_cachedInfo != null) return _cachedInfo!;

    final info = <String, String>{};

    // Get app package info
    try {
      final packageInfo = await PackageInfo.fromPlatform();
      info['app_version'] = packageInfo.version;
      info['build_number'] = packageInfo.buildNumber;
      info['package_name'] = packageInfo.packageName;
    } catch (e) {
      info['app_version'] = 'unknown';
      info['build_number'] = 'unknown';
      info['package_name'] = 'unknown';
    }

    // Get platform-specific device info
    try {
      if (Platform.isAndroid) {
        await _getAndroidInfo(info);
      } else if (Platform.isIOS) {
        await _getIosInfo(info);
      } else {
        info['platform'] = Platform.operatingSystem;
        info['os_version'] = Platform.operatingSystemVersion;
        info['model'] = 'unknown';
      }
    } catch (e) {
      info['platform'] = Platform.operatingSystem;
      info['os_version'] = 'unknown';
      info['model'] = 'unknown';
    }

    _cachedInfo = info;
    return info;
  }

  /// Get Android-specific device information.
  static Future<void> _getAndroidInfo(Map<String, String> info) async {
    final androidInfo = await _deviceInfoPlugin.androidInfo;

    info['platform'] = 'android';
    info['model'] = '${androidInfo.manufacturer} ${androidInfo.model}';
    info['os_version'] = androidInfo.version.release;
    info['sdk_version'] = androidInfo.version.sdkInt.toString();
    info['device_id'] = androidInfo.id;
    info['brand'] = androidInfo.brand;
    info['device'] = androidInfo.device;
    info['is_physical_device'] = androidInfo.isPhysicalDevice.toString();
  }

  /// Get iOS-specific device information.
  static Future<void> _getIosInfo(Map<String, String> info) async {
    final iosInfo = await _deviceInfoPlugin.iosInfo;

    info['platform'] = 'ios';
    info['model'] = iosInfo.model;
    info['os_version'] = iosInfo.systemVersion;
    info['device_name'] = iosInfo.name;
    info['device_id'] = iosInfo.identifierForVendor ?? 'unknown';
    info['system_name'] = iosInfo.systemName;
    info['is_physical_device'] = iosInfo.isPhysicalDevice.toString();
    info['utsname_machine'] = iosInfo.utsname.machine;
  }

  /// Get the app version string (e.g., "1.0.0").
  static Future<String> getAppVersion() async {
    try {
      final packageInfo = await PackageInfo.fromPlatform();
      return packageInfo.version;
    } catch (e) {
      return 'unknown';
    }
  }

  /// Get the full version string with build number (e.g., "1.0.0+1").
  static Future<String> getFullVersion() async {
    try {
      final packageInfo = await PackageInfo.fromPlatform();
      return '${packageInfo.version}+${packageInfo.buildNumber}';
    } catch (e) {
      return 'unknown';
    }
  }

  /// Get the platform name ('android' or 'ios').
  static String getPlatform() {
    if (Platform.isAndroid) return 'android';
    if (Platform.isIOS) return 'ios';
    return Platform.operatingSystem;
  }

  /// Whether the current platform is Android.
  static bool get isAndroid => Platform.isAndroid;

  /// Whether the current platform is iOS.
  static bool get isIOS => Platform.isIOS;

  /// Clear the cached info (useful for testing).
  static void clearCache() {
    _cachedInfo = null;
  }

  /// Get device info as HTTP headers for API requests.
  ///
  /// Returns a map suitable for adding to request headers:
  /// ```
  /// X-Device-Platform: android
  /// X-Device-Model: Samsung Galaxy S24
  /// X-Device-OS: 14
  /// X-App-Version: 1.0.0
  /// ```
  static Future<Map<String, String>> getDeviceHeaders() async {
    final info = await getDeviceInfo();
    return {
      'X-Device-Platform': info['platform'] ?? 'unknown',
      'X-Device-Model': info['model'] ?? 'unknown',
      'X-Device-OS': info['os_version'] ?? 'unknown',
      'X-App-Version': info['app_version'] ?? 'unknown',
    };
  }
}
