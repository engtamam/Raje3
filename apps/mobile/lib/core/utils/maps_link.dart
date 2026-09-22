import 'package:dio/dio.dart';

/// A pasted Google Maps link → {lat, lng}, or null when the link carries no coordinates.
///
/// SAME PATTERN LIST AS apps/console/src/googleMapsLink.ts, ported deliberately rather than
/// reimplemented — same regexes, same idea of what a real Maps link looks like.
///
/// WHY A LINK, NOT A MAP PICKER — console's own file header note holds here too: this product has
/// no mapping library and no basemap/tile provider anywhere. He already has his branch open in
/// Google Maps on his phone; copying its link is one tap he already knows how to do.
///
/// UNLIKE CONSOLE, THIS FILE DOES RESOLVE A SHORT LINK (`maps.app.goo.gl/...`,
/// `goo.gl/maps/...`) — found live, real-world: on a phone, the Google Maps app's own "Share"
/// button hands out exactly that short form by default; a desktop browser's address bar (what a
/// console user copies from) already gives the long form console's own file was written against.
/// A mobile user pasting the ONE link his phone actually gave him must not be told to go find a
/// different one. [resolveGoogleMapsLink] follows that link's redirect with a real HTTP client
/// (never [ApiClient]'s own instance — this talks to Google, never our own server, and must not
/// carry our auth/tenant headers) and reads the coordinates out of wherever it lands.
class ParsedLocation {
  final double lat;
  final double lng;
  const ParsedLocation({required this.lat, required this.lng});
}

const List<String> _shortLinkHosts = ['goo.gl', 'maps.app.goo.gl'];

/// Every shape Google's own share sheet and address bar actually produce, checked in the order a
/// real link is most likely to match. Each capture group is (lat, lng) in that order.
final List<RegExp> _patterns = [
  // .../@24.7136,46.6753,17z/... — the address-bar shape when you pan/zoom the map itself.
  RegExp(r'@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)'),
  // ?q=24.7136,46.6753 or &q=24.7136,46.6753 — the "share" shape for a plain dropped pin.
  RegExp(r'[?&]q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)'),
  // ?ll=24.7136,46.6753 — an older query shape, still produced by some Maps surfaces.
  RegExp(r'[?&]ll=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)'),
  // !3d24.7136!4d46.6753 — embedded in a place link's own data blob (.../place/.../data=...).
  RegExp(r'!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)'),
];

bool isShortGoogleMapsLink(String url) {
  final trimmed = url.trim();
  final uri = Uri.tryParse(trimmed);
  if (uri == null || uri.host.isEmpty) return false;
  final host = uri.host.replaceFirst(RegExp(r'^www\.'), '');
  return _shortLinkHosts.contains(host);
}

ParsedLocation? parseGoogleMapsLink(String url) {
  final trimmed = url.trim();
  if (trimmed.isEmpty) return null;
  for (final pattern in _patterns) {
    final match = pattern.firstMatch(trimmed);
    if (match == null) continue;
    final lat = double.tryParse(match.group(1)!);
    final lng = double.tryParse(match.group(2)!);
    if (lat != null && lng != null && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      return ParsedLocation(lat: lat, lng: lng);
    }
  }
  return null;
}

/// The full pipeline a caller actually wants: try the cheap sync parse first, and only reach for
/// the network when the link is a short one — never for an already-long link, and never a retry
/// loop for a genuinely wrong link. Returns `null` on any failure (an unreachable host, a
/// short-link host that isn't actually Google's, a redirect with no coordinates in it) — the
/// caller falls back to [isShortGoogleMapsLink]'s own distinct error message in that case.
Future<ParsedLocation?> resolveGoogleMapsLink(String url) async {
  final direct = parseGoogleMapsLink(url);
  if (direct != null) return direct;
  if (!isShortGoogleMapsLink(url)) return null;

  try {
    final dio = Dio();
    final response = await dio.get<dynamic>(
      url.trim(),
      options: Options(
        followRedirects: false,
        validateStatus: (status) => status != null && status < 400,
      ),
    );
    final location = response.headers.value('location');
    if (location != null) {
      final resolved = parseGoogleMapsLink(location);
      if (resolved != null) return resolved;
    }
    return parseGoogleMapsLink(response.realUri.toString());
  } on DioException {
    return null;
  }
}
