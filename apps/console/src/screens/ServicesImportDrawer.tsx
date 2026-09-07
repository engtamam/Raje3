/**
 * استيراد الخدمات والمنتجات من ملف CSV — `operations.bulk_import_services`.
 *
 * A PREVIEW, NEVER A ONE-CLICK APPLY. Money-adjacent (prices), and can touch the WHOLE catalogue
 * at once — same "loud, never silent" principle this product uses everywhere a batch of writes
 * could surprise the person who triggered it. The table below is computed client-side (against
 * the services already loaded in Services.tsx) BEFORE anything is sent, so an owner sees exactly
 * what will change — new / updated / a name repeated twice in his own file — and the button that
 * actually imports stays disabled until the file is clean.
 *
 * WHY A WHOLE FILE IS REFUSED FOR ONE BAD ROW, HERE TOO: the backend already refuses atomically
 * (staff.py::bulk_import_services's own docstring — a 422 from Pydantic before anything is
 * written), and re-deriving that same "no partial import" promise client-side, before a network
 * round trip, is what lets this screen show the reason immediately instead of after a wasted call.
 *
 * EXPECTED COLUMNS (English headers, case-insensitive — matches csv.ts's own lower-casing):
 *   name (required), price (ريال، اختياري), duration_minutes (اختياري), cycle_days (اختياري),
 *   external_id (اختياري — معرّف من نظام كاشير خارجي، يخلي إعادة تسمية الصف بدون تكراره),
 *   description (اختياري — سطر قصير، يُستبدل بالكامل كل استيراد، لا يُدمَج).
 *
 * A DOWNLOADABLE TEMPLATE, NOT A BLANK PAGE. An owner typing his own header row from memory is
 * exactly how "duration" and "duration_minutes" end up as two different files nobody can import —
 * `/templates/services-import-template.xlsx` (public/, generated once by
 * scripts/generate-services-import-template.py, never hand-edited) already carries the right
 * headers and one example row, so the only thing he has to get right is the values.
 */
import { useState } from 'react';
import { Download, Upload } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Drawer } from '../rj-ui/Drawer';
import { Toggle } from '../rj-ui/Toggle';
import { parseCsv, csvToObjects } from '../csv';
import { extractRowImages, readXlsxRows } from '../xlsx_images';
import { halalas } from '../money';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './services-i18n';

interface ExistingService { name: string; active?: boolean }

/** Internal status codes, translated only at render — same idiom as Bookings.tsx's own
 *  STATUS_LABEL: the value a translator would touch lives in services-i18n.ts, never in a TS
 *  string-literal type that a locale could never vary. */
type WillBe = 'new' | 'update' | 'reactivate';

interface ParsedRow {
  line: number;                 // 1-indexed, INCLUDING the header row, so it matches what a
                                // person counts when they open the file in a spreadsheet app
  name: string; price_minor: number; duration_minutes: number; cycle_days: number;
  external_id: string; description: string;
  // BLANK MEANS "NO PICTURE IN THIS ROW", never "clear the existing one" — see
  // ServiceImportRow.image_base64's own note on the server side; a CSV (which cannot carry a
  // picture at all) always leaves these blank.
  image_base64: string; image_content_type: string;
  error: string;                // '' = valid
  willBe: WillBe;
}

/** THE TEMPLATE'S OWN HEADERS ARE ARABIC WORDS, not `duration_minutes`/`cycle_days` — an owner who
 *  cannot read English should never have to type into a column named in it. The parser below
 *  still reads the plain English keys internally (`o.name`, `o.price`, …), so every column the
 *  file could carry is aliased here to its canonical key BEFORE anything else touches the row —
 *  one normalization, in one place, rather than every reader of `objs` learning both spellings.
 *  The English headers stay recognized too: a shop that kept an older file, or built its own from
 *  a memory of the old template, must not suddenly have every row read as empty. */
const HEADER_ALIASES: Record<string, string> = {
  name: 'name', 'الاسم': 'name',
  price: 'price', 'السعر': 'price',
  duration_minutes: 'duration_minutes', 'المدة (دقائق)': 'duration_minutes', 'المدة': 'duration_minutes',
  cycle_days: 'cycle_days', 'دورة التكرار (أيام)': 'cycle_days', 'دورة التكرار': 'cycle_days',
  external_id: 'external_id', 'معرّف خارجي': 'external_id', 'معرف خارجي': 'external_id',
  description: 'description', 'الوصف': 'description',
};

function normalizeHeaders(objs: Record<string, string>[]): Record<string, string>[] {
  return objs.map((o) => {
    const out: Record<string, string> = {};
    for (const [k, v] of Object.entries(o)) out[HEADER_ALIASES[k.trim()] ?? k] = v;
    return out;
  });
}

/** The shared core: a plain object per row (already extracted from EITHER a .csv's text or an
 *  .xlsx's cells — see `onFile` for which), plus whatever pictures an .xlsx anchored per row. */
function parseRowObjects(
  t: (key: string) => string, rawObjs: Record<string, string>[],
  images: Map<number, { base64: string; contentType: string }>, existing: ExistingService[],
): ParsedRow[] {
  const objs = normalizeHeaders(rawObjs);
  const byName = new Map(existing.map((s) => [s.name.trim().toLowerCase(), s]));
  const seenNames = new Set<string>();
  const dupeNames = new Set<string>();

  const rows: ParsedRow[] = objs.map((o, i) => {
    const line = i + 2;   // +1 for the header row, +1 for 1-indexing
    const name = (o.name ?? '').trim();
    const key = name.toLowerCase();
    if (key) {
      if (seenNames.has(key)) dupeNames.add(key);
      seenNames.add(key);
    }

    let error = '';
    if (!name) error = t('services.import.error.nameEmpty');

    const priceText = o.price ?? '';
    const priceMinor = priceText ? halalas(priceText) : 0;
    if (!error && priceText && priceMinor === null) error = t('services.import.error.priceInvalid');

    const durationText = o.duration_minutes ?? '';
    const duration = durationText ? Number(durationText) : 0;
    if (!error && durationText && (!Number.isInteger(duration) || duration < 0 || duration > 720)) {
      error = t('services.import.error.durationInvalid');
    }

    const cycleText = o.cycle_days ?? '';
    const cycle = cycleText ? Number(cycleText) : 0;
    if (!error && cycleText && (!Number.isInteger(cycle) || cycle < 0 || cycle > 3650)) {
      error = t('services.import.error.cycleInvalid');
    }

    const found = byName.get(key);
    const willBe: WillBe = found ? (found.active === false ? 'reactivate' : 'update') : 'new';

    const image = images.get(line);

    return {
      line, name, price_minor: priceMinor ?? 0, duration_minutes: duration, cycle_days: cycle,
      external_id: (o.external_id ?? '').trim(), description: (o.description ?? '').trim(),
      image_base64: image?.base64 ?? '', image_content_type: image?.contentType ?? '',
      error, willBe,
    };
  });

  // Second pass: a name repeated in the file is an error on EVERY row that carries it, not just
  // the second one — there is no "first row wins" here, the whole point is the file is ambiguous.
  return rows.map((r) => (
    !r.error && dupeNames.has(r.name.toLowerCase())
      ? { ...r, error: t('services.import.error.duplicateName') } : r
  ));
}

/** A .csv is always text-only — no pictures ride along, `parseRowObjects` gets an empty map. */
function parseCsvRows(t: (key: string) => string, text: string, existing: ExistingService[]): ParsedRow[] {
  return parseRowObjects(t, csvToObjects(parseCsv(text)), new Map(), existing);
}

/** An .xlsx's rows AND whatever pictures were anchored inside it, joined by spreadsheet line. */
async function parseXlsxRows(
  t: (key: string) => string, file: ArrayBuffer, existing: ExistingService[],
): Promise<ParsedRow[]> {
  const bytes = new Uint8Array(file);
  const [objs, images] = await Promise.all([readXlsxRows(bytes), extractRowImages(bytes)]);
  const byLine = new Map(images.map((i) => [i.row, { base64: i.base64, contentType: i.contentType }]));
  return parseRowObjects(t, objs, byLine, existing);
}

/** `willBe`'s screen text — a status code translated at the one place it is shown. */
function willBeLabel(t: (key: string) => string, willBe: WillBe): string {
  return {
    new: t('services.import.status.new'),
    update: t('services.import.status.update'),
    reactivate: t('services.import.status.reactivate'),
  }[willBe];
}

export function ServicesImportDrawer({ session, catalog, existing, open, onClose, onImported }: {
  session: Session; catalog: Catalog; existing: ExistingService[];
  open: boolean; onClose: () => void; onImported: () => void;
}) {
  const { t } = useOperatorI18n();
  const [fileName, setFileName] = useState('');
  const [rows, setRows] = useState<ParsedRow[] | null>(null);
  const [deactivateMissing, setDeactivateMissing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState<{ created: number; updated: number; reactivated: number; deactivated: number } | null>(null);

  const importAction = action(catalog, 'operations.bulk_import_services');
  const errorCount = rows?.filter((r) => r.error).length ?? 0;

  function reset() {
    setFileName(''); setRows(null); setDeactivateMissing(false); setError(''); setResult(null);
  }

  async function onFile(f: File) {
    setResult(null);
    setError('');
    setFileName(f.name);
    // THE EXTENSION DECIDES THE READER, NOT THE MIME TYPE — a browser's guess at a spreadsheet's
    // MIME type is inconsistent (an .xlsx dragged from some file managers arrives with a blank
    // `type`), while the extension the owner himself chose when saving is never ambiguous.
    if (/\.xlsx$/i.test(f.name)) {
      setRows(await parseXlsxRows(t, await f.arrayBuffer(), existing));
    } else {
      setRows(parseCsvRows(t, await f.text(), existing));
    }
  }

  async function doImport() {
    if (!importAction || !rows || errorCount > 0) return;
    setBusy(true);
    setError('');
    try {
      const body = await call<{ created: number; updated: number; reactivated: number; deactivated: number }>(
        session, importAction, {
          rows: rows.map((r) => ({
            name: r.name, price_minor: r.price_minor, duration_minutes: r.duration_minutes,
            cycle_days: r.cycle_days, external_id: r.external_id, description: r.description,
            image_base64: r.image_base64, image_content_type: r.image_content_type,
          })),
          deactivate_missing: deactivateMissing,
        });
      setResult(body);
      setRows(null);
      onImported();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('services.import.error.failed'));
    } finally {
      setBusy(false);
    }
  }

  const missingFromFile = rows
    ? existing.filter((s) => s.active !== false
        && !rows.some((r) => !r.error && r.name.toLowerCase() === s.name.trim().toLowerCase()))
    : [];

  return (
    <Drawer open={open} onClose={() => { onClose(); reset(); }} title={t('services.import.title')}
           subtitle={t('services.import.subtitle')}
           footer={
             rows && !result ? (
               <>
                 <Button type="button" variant="ghost" onClick={() => { onClose(); reset(); }}>{t('services.cancel')}</Button>
                 <Button type="button" disabled={busy || errorCount > 0 || rows.length === 0} onClick={doImport}>
                   {busy ? t('services.import.importing') : tf(t, 'services.import.importRows', { n: rows.length })}
                 </Button>
               </>
             ) : (
               <Button type="button" variant="ghost" onClick={() => { onClose(); reset(); }}>{t('services.import.close')}</Button>
             )
           }>
      <div className="flex flex-col gap-4">
        {result ? (
          <div className="flex flex-col gap-2 rounded-card border border-success bg-success-soft p-4 text-success-on-soft">
            <p className="font-semibold">{t('services.import.done.title')}</p>
            <p className="text-sm">
              {tf(t, 'services.import.done.summary', {
                created: result.created, updated: result.updated, reactivated: result.reactivated,
              })}
              {result.deactivated > 0 ? tf(t, 'services.import.done.deactivatedSuffix', { n: result.deactivated }) : ''}.
            </p>
          </div>
        ) : (
          <>
            {/* THE TEMPLATE, ABOVE THE PICKER — a real file to download and fill, not a column
                list to memorise. `download` names the saved file regardless of what the browser
                shows in its address bar for a static /public/ asset. */}
            <a href="/templates/services-import-template.xlsx"
               download={t('services.import.templateFileName')}
               className="flex items-center justify-center gap-1.5 self-center rounded-lg px-3 py-1.5
                          text-xs font-medium text-text-secondary transition-colors hover:bg-surface-2">
              <Download size={13} aria-hidden />
              {t('services.import.downloadTemplate')}
            </a>

            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-card border-2 border-dashed border-border-subtle p-8 text-center hover:bg-surface-2">
              <Upload size={24} className="text-text-muted" />
              <span className="text-sm font-medium">{fileName || t('services.import.chooseFile')}</span>
              <input type="file"
                    accept=".csv,.xlsx,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    className="hidden"
                    onChange={(e) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
            </label>

            {rows ? (
              <>
                {errorCount > 0 ? (
                  <p role="alert" className="text-danger text-sm">
                    {tf(t, 'services.import.rowsError', { n: errorCount })}
                  </p>
                ) : null}

                <div className="max-h-64 overflow-y-auto rounded-card border border-border-subtle">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-surface-2 text-text-secondary">
                      <tr>
                        <th className="p-2 text-start">{t('services.import.table.line')}</th>
                        <th className="p-2 text-start">{t('services.name')}</th>
                        <th className="p-2 text-start">{t('services.price.label')}</th>
                        <th className="p-2 text-start">{t('services.import.table.status')}</th>
                        <th className="p-2 text-start">{t('services.import.table.image')}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {rows.map((r) => (
                        <tr key={r.line} className={r.error ? 'bg-danger-soft' : undefined}>
                          <td className="p-2 tabular-nums">{r.line}</td>
                          <td className="p-2">{r.name || '—'}</td>
                          <td className="p-2 tabular-nums">{(r.price_minor / 100).toFixed(2)}</td>
                          <td className="p-2">{r.error || willBeLabel(t, r.willBe)}</td>
                          <td className="p-2 text-success">
                            {r.image_base64 ? t('services.import.table.hasImage') : ''}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {missingFromFile.length > 0 ? (
                  <div className="flex flex-col gap-2 rounded-card border border-warning bg-warning-soft p-3 text-sm">
                    <p className="font-medium text-warning-on-soft">
                      {tf(t, 'services.import.missingHeader', { n: missingFromFile.length })}
                    </p>
                    <p className="text-warning-on-soft">{missingFromFile.map((s) => s.name).join(t('services.import.listJoin'))}</p>
                    <div className="flex items-center justify-between">
                      <span>{t('services.import.deactivateLabel')}</span>
                      <Toggle checked={deactivateMissing} onChange={setDeactivateMissing}
                             ariaLabel={t('services.import.deactivateAria')} />
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}

            {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
          </>
        )}
      </div>
    </Drawer>
  );
}
