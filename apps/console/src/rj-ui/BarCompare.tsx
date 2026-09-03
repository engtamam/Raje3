/**
 * Our own BarCompare — component #15. Horizontal bars, relative to the largest value in the set
 * (never a fixed scale) — for comparing a handful of named things (branches, apps, marketers)
 * at a glance. Same hand-SVG-free, plain-div discipline as the rest of `rj-ui` — no chart
 * library, a bar is just a styled `<div>` at a computed width.
 */
export interface BarCompareItem {
  label: string;
  value: number;
}

export function BarCompare({ items, formatValue = String }: {
  items: BarCompareItem[];
  formatValue?: (v: number) => string;
}) {
  if (items.length === 0) {
    return <p className="text-sm text-text-secondary">لا بيانات للمقارنة بعد.</p>;
  }
  const max = Math.max(...items.map((i) => i.value), 1);
  return (
    <ul className="flex flex-col gap-2.5">
      {items.map((item) => {
        const pct = Math.max(2, Math.round((item.value / max) * 100));
        return (
          <li key={item.label} className="flex flex-col gap-1">
            <div className="flex items-center justify-between text-sm">
              <span className="text-text-primary">{item.label}</span>
              <span className="tabular-nums font-medium text-text-secondary">{formatValue(item.value)}</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-surface-2">
              <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
            </div>
          </li>
        );
      })}
    </ul>
  );
}
