/**
 * Our own AreaTrend — component #14, hand-drawn SVG in the same spirit as
 * `apps/console/src/screens/Shop.tsx`'s own `RetentionTrend` (no charting library anywhere in
 * this codebase, by decision — see the admin plan's own note). Generalised for the admin
 * dashboard's own repeated need (platform-wide retention trend, revenue trend, ...) rather than
 * one bespoke component per metric.
 *
 * A point with `value: null` is a real gap (too little data to trust, a metric not computed for
 * that period) — drawn as a break in the line, never bridged into a false continuity.
 */
export interface TrendPoint {
  label: string;
  value: number | null;
}

export function AreaTrend({ points, formatValue = String }: {
  points: TrendPoint[];
  /** How a value is spelled out under the newest point — e.g. `(v) => `${Math.round(v*100)}%`. */
  formatValue?: (v: number) => string;
}) {
  const W = 320, H = 90, PAD_X = 4, PAD_TOP = 12, PAD_BOTTOM = 16;
  const drawn = points.map((p) => p.value).filter((v): v is number => v !== null);

  if (drawn.length < 2) {
    return <p className="text-sm text-text-secondary">لا بيانات كافية لرسم اتجاه بعد.</p>;
  }

  const min = Math.min(...drawn), max = Math.max(...drawn);
  const span = max - min || 0.1;
  const x = (i: number) => PAD_X + (i / (points.length - 1)) * (W - PAD_X * 2);
  const y = (v: number) => H - PAD_BOTTOM - ((v - min) / span) * (H - PAD_TOP - PAD_BOTTOM);

  // One path per unbroken run of non-null points, same reasoning as Shop.tsx's own RetentionTrend.
  const runs: { x: number; y: number }[][] = [];
  let current: { x: number; y: number }[] = [];
  points.forEach((p, i) => {
    if (p.value === null) { if (current.length) runs.push(current); current = []; return; }
    current.push({ x: x(i), y: y(p.value) });
  });
  if (current.length) runs.push(current);

  const smoothPath = (run: { x: number; y: number }[]) => {
    if (run.length < 2) return `M ${run[0].x} ${run[0].y}`;
    let d = `M ${run[0].x} ${run[0].y}`;
    for (let i = 1; i < run.length; i++) {
      const mid = { x: (run[i - 1].x + run[i].x) / 2, y: (run[i - 1].y + run[i].y) / 2 };
      d += ` Q ${run[i - 1].x} ${run[i - 1].y} ${mid.x} ${mid.y}`;
    }
    const p = run.at(-1)!;
    d += ` T ${p.x} ${p.y}`;
    return d;
  };

  const longest = runs.reduce((a, b) => (b.length > a.length ? b : a), runs[0]);
  const first = longest[0], last = longest.at(-1)!;
  const areaPath = `${smoothPath(longest)} L ${last.x} ${H - PAD_BOTTOM} L ${first.x} ${H - PAD_BOTTOM} Z`;
  const lastValue = drawn.at(-1)!;

  return (
    <div className="flex flex-col gap-1">
      <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img"
           className="text-accent" aria-label={`اتجاه: ينتهي عند ${formatValue(lastValue)}`}>
        <defs>
          <linearGradient id="rj-area-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="currentColor" stopOpacity="0.22" />
            <stop offset="100%" stopColor="currentColor" stopOpacity="0" />
          </linearGradient>
        </defs>
        <path d={areaPath} fill="url(#rj-area-fill)" />
        {runs.map((run, i) => (
          <path key={i} d={smoothPath(run)} fill="none" stroke="currentColor"
               strokeWidth={2.25} strokeLinecap="round" />
        ))}
        <circle cx={last.x} cy={last.y} r={3.5} fill="currentColor" />
      </svg>
      <div dir="ltr" className="flex items-center justify-between px-1 text-[11px] font-medium text-text-secondary">
        <span>{points[0].label}</span>
        <span className="font-semibold text-text-primary">{formatValue(lastValue)}</span>
        <span>{points.at(-1)!.label}</span>
      </div>
    </div>
  );
}
