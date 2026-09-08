/**
 * سجل الأخطاء — every error the platform recorded, from its servers and from its users' browsers,
 * in one list.
 *
 * THE QUESTION IT ANSWERS. «الشاشة وقفت عند فلان» used to need a developer, a kubeconfig and
 * twenty minutes of `kubectl logs` on a pod that may already have been replaced. The error existed
 * for a quarter of a second inside a browser nobody will see again, or in a log line on a node that
 * has since rolled. This is that, kept for ten days, filterable.
 *
 * ONE LIST, NOT TWO TABS. A browser error and a pod's stack trace are the same question asked from
 * two places, and error-collector stores them in one collection precisely so a reader is not asked
 * to guess which half to look in. `source` is a badge and a filter, never a separate screen.
 *
 * THE FILTERS ARE BUILT FROM THE DATA, NEVER FROM A LIST IN THIS FILE. `GET /api/v1/signals`
 * returns the distinct `sources`, `severities` and `services` present alongside the page, and the
 * checkboxes below are rendered from those. That is the console half of the collector's own design
 * decision to keep both columns free-form strings: the day something starts posting `warning`, or a
 * mobile app starts posting `source: "mobile_app"`, the checkbox appears on the next page load with
 * no release of this file.
 *
 * `error` IS CHECKED BY DEFAULT AND THE OTHERS ARE NOT — the screen is called «سجل الأخطاء» and an
 * operator opening it is not asking to read every `info` breadcrumb the fleet ever emitted. It is a
 * default, visibly, in a checkbox he can clear; never a filter applied behind his back.
 */
import { useEffect, useMemo, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';
import { western } from '../digits';

export interface Signal {
  id: string;
  received_at: number;
  occurred_at: number;
  source: string;
  severity: string;
  service: string;
  status_code: number | null;
  request_id: string;
  message: string;
  detail: Record<string, unknown> | null;
  context: Record<string, unknown> | null;
}

interface SignalsPage {
  signals: Signal[];
  next_cursor: string | null;
  sources: string[];
  severities: string[];
  services: string[];
}

/** THE DEFAULT WINDOW. An error store ten days deep opened with no window at all shows the whole
 *  ten days, and the row an operator is looking for is the one that happened while he was on the
 *  phone. A day is the honest first question; the field is a plain number of hours he can widen. */
const DEFAULT_HOURS = 24;

/** A tone per severity, so the eye sorts the list before the reader does. An unknown severity —
 *  and there WILL be unknown severities, that is the whole point of the free-form column — gets
 *  the neutral tone rather than being hidden or crashing the row. */
function severityTone(severity: string): 'danger' | 'warning' | 'info' | 'neutral' {
  const s = severity.toLowerCase();
  if (s === 'error' || s === 'fatal' || s === 'critical') return 'danger';
  if (s === 'warning' || s === 'warn') return 'warning';
  if (s === 'info' || s === 'debug') return 'info';
  return 'neutral';
}

function whenText(epochSeconds: number): string {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleString('ar-SA');
}

/** ONE ROW AS PLAIN TEXT — the format both copy buttons produce, so a row copied on its own and
 *  the same row inside a bulk copy are byte-identical. A support thread that quotes one and a
 *  ticket that quotes the other must not look like two different incidents. */
export function signalToText(s: Signal): string {
  const lines = [
    `[${whenText(s.received_at)}] ${s.severity} · ${s.source} · ${s.service}`,
    s.status_code != null ? `status: ${s.status_code}` : '',
    s.request_id ? `request_id: ${s.request_id}` : '',
    s.message,
    s.detail ? `detail: ${JSON.stringify(s.detail)}` : '',
    s.context ? `context: ${JSON.stringify(s.context)}` : '',
  ];
  return lines.filter(Boolean).join('\n');
}

export function AdminSignals({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const listAction = catalog.services.flatMap((s) => s.actions).find((a) => a.id === 'errors.list');
  if (!listAction) {
    // NOT A MISSING TAB. See NoActionAvailable's own header: «the action is missing» and «I lack
    // the capability» are different facts, and error-collector being undeployed is exactly the
    // case that must not read as a permissions problem.
    return <NoActionAvailable catalog={catalog} permissionTitle="سجل الأخطاء ليس ضمن صلاحياتك." />;
  }
  return <SignalsList session={session} action={listAction} />;
}

function SignalsList({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [page, setPage] = useState<SignalsPage | 'loading' | 'failed'>('loading');
  // The filter lists persist across reloads: narrowing to one source must not make every OTHER
  // checkbox vanish, which is what happens if the options are read from the current page alone.
  const [known, setKnown] = useState<{ sources: string[]; severities: string[]; services: string[] }>(
    { sources: [], severities: [], services: [] });

  const [sources, setSources] = useState<string[]>([]);
  const [severities, setSeverities] = useState<string[]>(['error']);
  const [service, setService] = useState('');
  const [hours, setHours] = useState(String(DEFAULT_HOURS));
  const [q, setQ] = useState('');
  const [open, setOpen] = useState<Record<string, boolean>>({});
  const [copied, setCopied] = useState('');

  async function search() {
    setPage('loading');
    const params = new URLSearchParams();
    for (const s of sources) params.append('source', s);
    for (const s of severities) params.append('severity', s);
    if (service.trim()) params.set('service', service.trim());
    const h = Number(hours);
    if (Number.isFinite(h) && h > 0) {
      params.set('since', String(Math.floor(Date.now() / 1000) - Math.floor(h * 3600)));
    }
    if (q.trim()) params.set('q', q.trim());
    params.set('limit', '200');
    try {
      const body = await req<SignalsPage>(
        `${action.path}?${params.toString()}`, 'GET', undefined, session.access_token);
      setPage(body);
      // UNION, NEVER REPLACE — see the note on `known` above.
      setKnown((prev) => ({
        sources: union(prev.sources, body.sources),
        severities: union(prev.severities, body.severities),
        services: union(prev.services, body.services),
      }));
    } catch {
      setPage('failed');
    }
  }

  useEffect(() => { search(); }, []); // eslint-disable-line react-hooks/exhaustive-deps -- first load, defaults only

  const rows = page === 'loading' || page === 'failed' ? [] : page.signals;

  const allText = useMemo(() => rows.map(signalToText).join('\n\n———\n\n'), [rows]);

  async function copy(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(label);
      // NO TIMER TO CLEAR ON UNMOUNT — the confirmation is cleared by the next copy or the next
      // search, so there is no pending callback to leak if the operator leaves the tab.
    } catch {
      // A browser that refuses the clipboard (an insecure origin, a denied permission) must not
      // throw into a screen whose whole job is showing what threw.
      setCopied('');
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">سجل الأخطاء</h1>
      <p className="text-sm text-text-secondary">
        كل خطأ سجّلته المنصة — من خوادمها ومن متصفحات المستخدمين — في مكان واحد. يُحفظ عشرة أيام
        ثم يُمحى تلقائياً.
      </p>

      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); setCopied(''); search(); }}>
        <CheckboxRow label="المصدر" options={known.sources} selected={sources} onChange={setSources} />
        <CheckboxRow label="الشدّة" options={known.severities} selected={severities} onChange={setSeverities} />
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className="text-label font-medium text-text-secondary">الخدمة</span>
            <Input dir="ltr" list="signals-services" value={service}
                   onChange={(e) => setService(e.target.value)} />
            <datalist id="signals-services">
              {known.services.map((s) => <option key={s} value={s} />)}
            </datalist>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-label font-medium text-text-secondary">آخر كم ساعة</span>
            <Input dir="ltr" inputMode="numeric" value={hours}
                   onChange={(e) => setHours(western(e.target.value))} />
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-label font-medium text-text-secondary">بحث بالنص</span>
            <Input dir="ltr" value={q} onChange={(e) => setQ(e.target.value)} />
          </label>
        </div>
        <div className="flex items-center gap-2">
          <Button type="submit">بحث</Button>
          <Button type="button" variant="outline" disabled={rows.length === 0}
                  onClick={() => copy(allText, `نُسخ ${rows.length}`)}>
            نسخ الكل
          </Button>
          {copied ? <span className="text-label text-success">{copied}</span> : null}
        </div>
      </form>

      {page === 'loading' ? (
        <p className="text-sm text-text-secondary" aria-busy="true">جارٍ التحميل…</p>
      ) : page === 'failed' ? (
        <p role="alert" className="text-danger text-sm">تعذّرت قراءة سجل الأخطاء.</p>
      ) : rows.length === 0 ? (
        // «لا أخطاء بهذي الفلاتر» — a fact about the filters, never «كل شيء سليم». The two read
        // identically to a tired operator and only one of them is something he can act on.
        <p className="text-sm text-text-secondary">لا أخطاء بهذي الفلاتر.</p>
      ) : (
        <div className="flex flex-col gap-2">
          {rows.map((s) => (
            <article key={s.id}
                     className="flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-4">
              <div className="flex flex-wrap items-center gap-2">
                <span dir="ltr" className="text-label text-text-secondary">{whenText(s.received_at)}</span>
                <Badge tone="neutral">{s.source}</Badge>
                <Badge tone={severityTone(s.severity)}>{s.severity}</Badge>
                <span className="text-sm font-medium">{s.service}</span>
                {/* BLANK WHEN NULL, never 0. A signal with no status code did not answer 0. */}
                {s.status_code != null ? (
                  <span dir="ltr" className="text-label text-text-secondary">HTTP {s.status_code}</span>
                ) : null}
                {s.request_id ? (
                  <span dir="ltr" className="text-label text-text-secondary">{s.request_id}</span>
                ) : null}
              </div>
              <p dir="ltr" className="whitespace-pre-wrap break-words text-sm">{s.message}</p>
              <div className="flex items-center gap-2">
                {s.detail || s.context ? (
                  <Button type="button" size="sm" variant="ghost"
                          aria-expanded={Boolean(open[s.id])}
                          onClick={() => setOpen((p) => ({ ...p, [s.id]: !p[s.id] }))}>
                    {open[s.id] ? 'إخفاء التفاصيل' : 'التفاصيل'}
                  </Button>
                ) : null}
                <Button type="button" size="sm" variant="ghost"
                        onClick={() => copy(signalToText(s), 'نُسخ السطر')}>
                  نسخ
                </Button>
              </div>
              {open[s.id] ? (
                // RENDERED GENERICALLY, on purpose. `detail` and `context` are free-form blobs
                // written by whatever emitted the signal; a component that knew their keys would be
                // a component that renders nothing the day a new emitter arrives.
                <pre dir="ltr"
                     className="overflow-x-auto rounded-md bg-surface-2 p-3 text-label leading-relaxed">
                  {JSON.stringify({ detail: s.detail, context: s.context }, null, 2)}
                </pre>
              ) : null}
            </article>
          ))}
        </div>
      )}
    </div>
  );
}

function union(a: string[], b: string[]): string[] {
  return Array.from(new Set([...a, ...b])).sort();
}

function CheckboxRow({ label, options, selected, onChange }: {
  label: string; options: string[]; selected: string[]; onChange: (v: string[]) => void;
}) {
  // NOTHING TO OFFER IS NOT AN EMPTY BOX. Before the first page arrives there are no known values,
  // and an empty fieldset with a heading reads as «no sources exist».
  if (options.length === 0) return null;
  return (
    <fieldset className="flex flex-wrap items-center gap-3">
      <legend className="text-label font-medium text-text-secondary">{label}</legend>
      {options.map((opt) => (
        <label key={opt} className="flex items-center gap-1.5 text-sm">
          <input
            type="checkbox"
            checked={selected.includes(opt)}
            onChange={(e) => onChange(e.target.checked
              ? [...selected, opt]
              : selected.filter((v) => v !== opt))}
          />
          <span dir="ltr">{opt}</span>
        </label>
      ))}
    </fieldset>
  );
}
