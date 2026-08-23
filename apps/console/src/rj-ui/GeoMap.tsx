/**
 * Our own GeoMap — component #17, and deliberately NOT a real map. No mapping library exists in
 * this codebase and the admin plan's own rule (§٣ of the components list) is not to add one — a
 * real basemap needs tiles, an API key, and a network fetch a self-contained SVG component
 * cannot honestly promise. This is a SCATTER PROJECTION: points placed by their own
 * lat/lng, normalised to the bounding box of the data itself (not a real map projection), with
 * city labels doing the actual geographic orientation.
 *
 * GOOD ENOUGH FOR ITS ONE JOB — showing where prospects/shops cluster relative to each other —
 * and no more than that. A screen that needs street-level accuracy needs a real map, not this.
 */
export interface GeoPoint {
  id: string;
  lat: number;
  lng: number;
  label: string;
  /** Groups points into a labelled legend — e.g. a city or a status. */
  group?: string;
}

const GROUP_TEXT_COLORS = ['text-accent', 'text-success', 'text-warning', 'text-danger', 'text-text-muted'];
const GROUP_BG_COLORS = ['bg-accent', 'bg-success', 'bg-warning', 'bg-danger', 'bg-text-muted'];

export function GeoMap({ points }: { points: GeoPoint[] }) {
  if (points.length === 0) {
    return <p className="text-sm text-text-secondary">لا مواقع لعرضها بعد.</p>;
  }

  const lats = points.map((p) => p.lat), lngs = points.map((p) => p.lng);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLng = Math.min(...lngs), maxLng = Math.max(...lngs);
  const latSpan = maxLat - minLat || 1, lngSpan = maxLng - minLng || 1;

  const W = 320, H = 220, PAD = 16;
  // Latitude increases northward but SVG y increases downward — flip it, or "north" points south.
  const x = (lng: number) => PAD + ((lng - minLng) / lngSpan) * (W - PAD * 2);
  const y = (lat: number) => H - PAD - ((lat - minLat) / latSpan) * (H - PAD * 2);

  const groups = Array.from(new Set(points.map((p) => p.group).filter((g): g is string => Boolean(g))));
  const textColorFor = (group?: string) => {
    if (!group) return GROUP_TEXT_COLORS[0];
    const i = groups.indexOf(group);
    return GROUP_TEXT_COLORS[i % GROUP_TEXT_COLORS.length];
  };

  return (
    <div className="flex flex-col gap-2">
      <svg width="100%" viewBox={`0 0 ${W} ${H}`} className="rounded-md bg-surface-2" role="img"
           aria-label={`خريطة توزيع ${points.length} موقعاً`}>
        {points.map((p) => (
          <circle key={p.id} cx={x(p.lng)} cy={y(p.lat)} r={4} className={`${textColorFor(p.group)} opacity-80`}
                 fill="currentColor">
            <title>{p.label}</title>
          </circle>
        ))}
      </svg>
      {groups.length > 0 ? (
        <ul className="flex flex-wrap gap-3 text-xs text-text-secondary">
          {groups.map((g, i) => (
            <li key={g} className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${GROUP_BG_COLORS[i % GROUP_BG_COLORS.length]}`} />
              {g}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
