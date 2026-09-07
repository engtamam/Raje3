/**
 * Our own Heatmap — component #16. A grid of shaded cells (weekday × hour, or any two labelled
 * axes), same spirit as `Shop.tsx`'s own `PeakHeatmap`/`EntityDayHeatmap` but generalised — for
 * the admin dashboard's own platform-wide peak-time view. Intensity is relative to the highest
 * cell in the WHOLE grid, never per-row, so rows stay comparable to each other.
 */
export interface HeatmapCell {
  row: string;
  col: string;
  value: number;
}

export function Heatmap({ rows, cols, cells, formatValue = String }: {
  rows: string[];
  cols: string[];
  cells: HeatmapCell[];
  formatValue?: (v: number) => string;
}) {
  const max = Math.max(...cells.map((c) => c.value), 1);
  const at = (r: string, c: string) => cells.find((cell) => cell.row === r && cell.col === c)?.value ?? 0;

  if (rows.length === 0 || cols.length === 0) {
    return <p className="text-sm text-text-secondary">لا بيانات كافية بعد.</p>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="border-separate" style={{ borderSpacing: 3 }}>
        <thead>
          <tr>
            <th aria-hidden />
            {cols.map((c) => (
              <th key={c} className="px-1 text-center text-[10px] font-normal text-text-secondary">{c}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r}>
              <th scope="row" className="whitespace-nowrap pe-2 text-start text-xs font-normal text-text-secondary">{r}</th>
              {cols.map((c) => {
                const v = at(r, c);
                const opacity = v === 0 ? 0.06 : 0.15 + (v / max) * 0.85;
                return (
                  <td key={c} title={`${r} · ${c}: ${formatValue(v)}`}>
                    <div className="h-5 w-5 rounded-sm bg-info" style={{ opacity }} />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
