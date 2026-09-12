/**
 * The staff-comparison quadrant — quality (Y) × engagement rate (X), bubble size = visit volume.
 * A real React port of the approved mockup (rating-app-screen-pitch-violet.html), not a
 * screenshot of it: same axes, same four status zones, same click-and-hover pair.
 *
 * WHY A QUADRANT AND NOT A LEADERBOARD ALONE. A raw star-average ranking punishes a busy
 * operator's larger sample and rewards one who barely gets rated at all — the owner's own
 * repeated correction this session. Two separate numbers, plotted together, read fairly: a small,
 * excellent sample and a large, excellent sample both land in the same "top" zone; neither is
 * misrepresented as the other's rival.
 *
 * STATUS COLOUR CARRIES A REAL MANAGEMENT STATE, never "series identity" — every bubble is the
 * same brand-violet fill; the zone TINT behind it plus its own text label carry the meaning
 * (dataviz skill's own rule: a status colour never appears without an icon/label beside it — the
 * legend below the chart is that label, always visible, never color alone).
 *
 * BOTH INTERACTIONS COEXIST — click selects a bubble into the persistent, touch-friendly detail
 * panel (works with a finger on the tablet this console's field screen already targets); hover
 * shows a lightweight, mouse-only tooltip that follows the pointer. Neither replaces the other.
 */
import { useState } from 'react';
import { useOperatorI18n, tf } from '../operator-i18n';
import './staff-quadrant-i18n';

export interface StaffQuadrantRow {
  operator_id: string;
  operator_name: string;
  visits: number;
  ratings: number;
  average_rating: number;
}

const Q_THRESHOLD = 4.5;
const E_THRESHOLD = 0.40;
const Y_MIN = 2.5, Y_MAX = 5.0;
const X_MIN = 0, X_MAX = 0.60;
const PAD = { l: 38, r: 14, t: 12, b: 32 };
// A SMALL, FIXED CANVAS ON PURPOSE — the mockup's own "compact, not a tall centerpiece" call.
const W = 520, H = 300;
const PLOT_W = W - PAD.l - PAD.r, PLOT_H = H - PAD.t - PAD.b;

const xPos = (rate: number) => PAD.l + (rate - X_MIN) / (X_MAX - X_MIN) * PLOT_W;
const yPos = (avg: number) => PAD.t + (1 - (avg - Y_MIN) / (Y_MAX - Y_MIN)) * PLOT_H;
const rPos = (visits: number) => 7 + Math.sqrt(Math.max(visits, 0)) * 1.5;

// dataviz skill's own status palette (good/warning/serious/critical), applied as zone tints.
const ZONES = {
  star: { color: '#0ca30c', labelKey: 'rating.quadrant.zone.star' },
  hiddenGem: { color: '#fab219', labelKey: 'rating.quadrant.zone.hiddenGem' },
  needsCoaching: { color: '#ec835a', labelKey: 'rating.quadrant.zone.needsCoaching' },
  needsSupport: { color: '#d03b3b', labelKey: 'rating.quadrant.zone.needsSupport' },
} as const;

function zoneOf(row: StaffQuadrantRow, rate: number): typeof ZONES[keyof typeof ZONES] {
  const highQ = row.average_rating >= Q_THRESHOLD, highE = rate >= E_THRESHOLD;
  if (highQ && highE) return ZONES.star;
  if (highQ && !highE) return ZONES.hiddenGem;
  if (!highQ && highE) return ZONES.needsCoaching;
  return ZONES.needsSupport;
}

export function StaffQuadrant({ rows }: { rows: StaffQuadrantRow[] }) {
  const { t } = useOperatorI18n();
  const [selected, setSelected] = useState<string | null>(null);
  const [hover, setHover] = useState<{ x: number; y: number; row: StaffQuadrantRow; rate: number } | null>(null);

  const withRate = rows.map((r) => ({ row: r, rate: r.visits > 0 ? r.ratings / r.visits : 0 }));
  const xThresh = xPos(E_THRESHOLD), yThresh = yPos(Q_THRESHOLD);
  const selectedEntry = withRate.find((e) => e.row.operator_id === selected);

  return (
    <div className="flex flex-col gap-2 sm:grid sm:grid-cols-[1fr_240px] sm:items-stretch sm:gap-3">
      <div className="relative max-w-[560px] rounded-card border border-border-subtle bg-surface-1 p-3 pb-1.5">
        <svg
          viewBox={`0 0 ${W} ${H}`} role="img"
          aria-label={t('rating.quadrant.ariaLabel')}
          className="block w-full overflow-visible"
        >
          {/* zone backgrounds — very light tints, never the only carrier of meaning */}
          <rect x={PAD.l} y={PAD.t} width={xThresh - PAD.l} height={yThresh - PAD.t} fill={ZONES.hiddenGem.color} opacity={0.07} />
          <rect x={xThresh} y={PAD.t} width={PAD.l + PLOT_W - xThresh} height={yThresh - PAD.t} fill={ZONES.star.color} opacity={0.07} />
          <rect x={PAD.l} y={yThresh} width={xThresh - PAD.l} height={PAD.t + PLOT_H - yThresh} fill={ZONES.needsSupport.color} opacity={0.07} />
          <rect x={xThresh} y={yThresh} width={PAD.l + PLOT_W - xThresh} height={PAD.t + PLOT_H - yThresh} fill={ZONES.needsCoaching.color} opacity={0.07} />

          <line x1={xThresh} y1={PAD.t} x2={xThresh} y2={PAD.t + PLOT_H} className="stroke-border-strong" strokeWidth={1.5} strokeDasharray="4 4" />
          <line x1={PAD.l} y1={yThresh} x2={PAD.l + PLOT_W} y2={yThresh} className="stroke-border-strong" strokeWidth={1.5} strokeDasharray="4 4" />

          <line x1={PAD.l} y1={PAD.t + PLOT_H} x2={PAD.l + PLOT_W} y2={PAD.t + PLOT_H} className="stroke-border-strong" strokeWidth={1.5} />
          <line x1={PAD.l} y1={PAD.t} x2={PAD.l} y2={PAD.t + PLOT_H} className="stroke-border-strong" strokeWidth={1.5} />
          {[0, 0.3, 0.6].map((v) => (
            <text key={v} x={xPos(v)} y={PAD.t + PLOT_H + 15} textAnchor="middle" className="fill-text-muted text-[10px] tabular-nums">
              %{Math.round(v * 100)}
            </text>
          ))}
          {[3, 4, 5].map((v) => (
            <text key={v} x={PAD.l - 6} y={yPos(v) + 3} textAnchor="end" className="fill-text-muted text-[10px] tabular-nums">
              {v}
            </text>
          ))}
          <text x={PAD.l + PLOT_W / 2} y={H - 3} textAnchor="middle" className="fill-text-secondary text-[11px]">
            {t('rating.quadrant.xAxis')}
          </text>
          <text x={11} y={PAD.t + PLOT_H / 2} textAnchor="middle" transform={`rotate(-90 11 ${PAD.t + PLOT_H / 2})`}
                className="fill-text-secondary text-[11px]">
            {t('rating.quadrant.yAxis')}
          </text>

          {withRate.map(({ row, rate }) => {
            const cx = xPos(rate), cy = yPos(row.average_rating), r = rPos(row.visits);
            const zone = zoneOf(row, rate);
            const isSelected = row.operator_id === selected;
            return (
              <g
                key={row.operator_id}
                className="cursor-pointer"
                tabIndex={0}
                role="button"
                aria-label={row.operator_name}
                onClick={() => setSelected(row.operator_id)}
                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setSelected(row.operator_id); }}
                onMouseEnter={() => setHover({ x: cx, y: cy, row, rate })}
                onMouseMove={() => setHover({ x: cx, y: cy, row, rate })}
                onMouseLeave={() => setHover(null)}
              >
                <circle cx={cx} cy={cy} r={r} className="fill-accent" fillOpacity={0.22}
                        stroke={zone.color} strokeWidth={isSelected ? 4 : 2.5} />
                <circle cx={cx} cy={cy} r={3.5} className="fill-accent" />
                <text x={cx} y={cy - r - 6} textAnchor="middle"
                      className="fill-text-primary stroke-surface-1 text-[11.5px] font-bold"
                      style={{ paintOrder: 'stroke', strokeWidth: 3 }}>
                  {row.operator_name}
                </text>
              </g>
            );
          })}
        </svg>

        {hover ? (
          <div
            className="pointer-events-none absolute z-10 whitespace-nowrap rounded-lg bg-text-primary px-2.5 py-1.5 text-[11.5px] leading-relaxed text-surface-0 shadow-lg"
            style={{ left: hover.x, top: hover.y, transform: 'translate(-50%, -112%)' }}
          >
            <b className="text-accent">{hover.row.operator_name}</b> — {t(zoneOf(hover.row, hover.rate).labelKey)}
            <br />
            {tf(t, 'rating.quadrant.hoverLine', {
              visits: hover.row.visits, ratings: hover.row.ratings,
              rate: Math.round(hover.rate * 100), avg: hover.row.average_rating.toFixed(1),
            })}
          </div>
        ) : null}
      </div>

      <div className="flex flex-col gap-2 self-start rounded-card border border-border-subtle bg-surface-1 p-4">
        {selectedEntry ? (
          <>
            <p className="m-0 text-base font-bold">{selectedEntry.row.operator_name}</p>
            <span
              className="inline-flex w-fit items-center gap-1.5 rounded-full px-2.5 py-1 text-[11.5px] font-bold"
              style={{ background: `${zoneOf(selectedEntry.row, selectedEntry.rate).color}22`,
                      color: zoneOf(selectedEntry.row, selectedEntry.rate).color }}
            >
              {t(zoneOf(selectedEntry.row, selectedEntry.rate).labelKey)}
            </span>
            <DetailRow label={t('rating.quadrant.visits')} value={String(selectedEntry.row.visits)} />
            <DetailRow label={t('rating.quadrant.ratings')} value={String(selectedEntry.row.ratings)} />
            <DetailRow label={t('rating.quadrant.engagementRate')} value={`%${Math.round(selectedEntry.rate * 100)}`} />
            <DetailRow label={t('rating.quadrant.averageRating')} value={selectedEntry.row.average_rating.toFixed(1)} />
          </>
        ) : (
          <p className="m-auto text-center text-xs text-text-secondary">{t('rating.quadrant.emptyDetail')}</p>
        )}
      </div>
    </div>
  );
}

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between text-xs text-text-secondary">
      <span>{label}</span>
      <b className="tabular-nums text-text-primary">{value}</b>
    </div>
  );
}

/** The always-visible legend — every zone's own colour AND its own label, side by side; a status
 *  colour never appears here alone. */
export function StaffQuadrantLegend() {
  const { t } = useOperatorI18n();
  return (
    <div className="flex flex-wrap gap-x-5 gap-y-2 text-xs text-text-secondary">
      {Object.values(ZONES).map((z) => (
        <span key={z.labelKey} className="inline-flex items-center gap-1.5">
          <i className="inline-block size-2.5 shrink-0 rounded-sm" style={{ background: z.color }} aria-hidden />
          {t(z.labelKey)}
        </span>
      ))}
    </div>
  );
}
