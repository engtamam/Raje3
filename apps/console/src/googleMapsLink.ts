/**
 * A pasted Google Maps link → {lat, lng}, or null when the link does not carry coordinates.
 *
 * WHY A LINK, NOT A MAP PICKER. This product has no mapping library and no basemap/tile provider
 * anywhere (see rj-ui/GeoMap.tsx's own docstring — it is a read-only SVG scatter, not an
 * interactive map). Building a real picker means a tile provider, an API key, a bundle-size
 * trade — real infrastructure a shop's owner locating his own branch does not need: he already
 * has his branch open in Google Maps on his phone, and copying its link is one tap he already
 * knows how to do. Parsing that link locally costs nothing and needs no key at all.
 *
 * WHAT THIS DOES NOT HANDLE, ON PURPOSE: a SHORT link (maps.app.goo.gl/..., goo.gl/maps/...)
 * carries no coordinates in the URL itself — Google resolves those server-side on click, which
 * this function cannot do without a network call this product has no reason to make just to open
 * a branch. `parseGoogleMapsLink` returns null for one, and the caller's own error message says
 * so by name ("الصق الرابط الكامل من خرائط جوجل، لا الرابط المختصر") rather than a generic
 * "invalid link" that leaves an owner pasting the same short link three times.
 */

const SHORT_LINK_HOSTS = ['goo.gl', 'maps.app.goo.gl'];

/** Every shape Google's own share sheet and address bar actually produce, checked in the order a
 *  real link is most likely to match. Each capture group is (lat, lng) in that order. */
const PATTERNS: RegExp[] = [
  // .../@24.7136,46.6753,17z/... — the address-bar shape when you pan/zoom the map itself.
  /@(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)/,
  // ?q=24.7136,46.6753 or &q=24.7136,46.6753 — the "share" shape for a plain dropped pin.
  /[?&]q=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)/,
  // ?ll=24.7136,46.6753 — an older query shape, still produced by some Maps surfaces.
  /[?&]ll=(-?\d{1,3}\.\d+),(-?\d{1,3}\.\d+)/,
  // !3d24.7136!4d46.6753 — embedded in a place link's own data blob (.../place/.../data=...).
  /!3d(-?\d{1,3}\.\d+)!4d(-?\d{1,3}\.\d+)/,
];

export interface ParsedLocation {
  lat: number;
  lng: number;
}

export function isShortGoogleMapsLink(url: string): boolean {
  try {
    const host = new URL(url.trim()).hostname.replace(/^www\./, '');
    return SHORT_LINK_HOSTS.includes(host);
  } catch {
    return false;
  }
}

/** The full pipeline a caller actually wants: the cheap sync parse first, and only reach for the
 *  server (via [resolver], `api.ts`'s own `resolveMapsShortLink` — this file stays free of the
 *  network layer) when the link is a short one. Returns `null` on any failure exactly like
 *  [parseGoogleMapsLink] does, so a caller's existing "not resolved" branch already handles it. */
export async function resolveGoogleMapsLink(
  url: string,
  resolver: (url: string) => Promise<string>,
): Promise<ParsedLocation | null> {
  const direct = parseGoogleMapsLink(url);
  if (direct) return direct;
  if (!isShortGoogleMapsLink(url)) return null;
  try {
    const resolvedUrl = await resolver(url);
    return resolvedUrl ? parseGoogleMapsLink(resolvedUrl) : null;
  } catch {
    return null;
  }
}

export function parseGoogleMapsLink(url: string): ParsedLocation | null {
  const trimmed = url.trim();
  if (!trimmed) return null;
  for (const pattern of PATTERNS) {
    const m = trimmed.match(pattern);
    if (!m) continue;
    const lat = Number(m[1]);
    const lng = Number(m[2]);
    if (Number.isFinite(lat) && Number.isFinite(lng)
        && lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180) {
      return { lat, lng };
    }
  }
  return null;
}
