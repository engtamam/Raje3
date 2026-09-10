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
 * checkboxes/select below are built from those. That is the console half of the collector's own
 * design decision to keep those columns free-form strings: the day something starts posting
 * `warning`, or a mobile app starts posting `source: "mobile_app"`, the option appears on the next
 * page load with no release of this file.
 *
 * NO FILTER APPLIED ON THE FIRST LOAD, ON PURPOSE. An earlier version pre-checked `error` and
 * silently defaulted to the last 24 hours — so the very first thing a non-technical operator saw
 * could be an empty «لا أخطاء بهذي الفلاتر» with no visible reason (the severity checkboxes are
 * themselves BUILT from a page that already came back empty, so nothing explained the filter that
 * caused it). The screen now opens on the truest answer to «سجّل الأخطاء» — everything the store
 * holds — and narrowing is something the operator does, visibly, never something that happened to
 * him before he asked.
 *
 * SERVICE AND DURATION ARE REAL CHOICES, NEVER TYPING. A free-text box next to a table of exact
 * service names invited a typo that silently returned nothing; a plain number of hours asked a
 * non-technical operator to know what "24" versus "72" even means. Both are now closed lists — the
 * service `<Select>` built from what the store actually holds, the duration a handful of named
 * presets. Choosing either re-searches IMMEDIATELY, no separate «بحث» press — a select the operator
 * must then also confirm is the second half of the same «الصفحة تفرض عليه الحفظ» complaint the
 * free-text fields were the first half of. Severity/source stay checkboxes needing the button (a
 * multi-select toggle set has no single "changed" moment worth auto-firing on).
 *
 * A REAL TABLE, NOT A STACK OF EXPANDABLE CARDS — the earlier shape hid most of a row behind a
 * «التفاصيل» toggle a non-technical reader had to discover first. Every column that matters sits in
 * view, colour-coded so the eye sorts before the reader does: severity/status/source/service each
 * get their own badge tone (`rj-ui/Table`'s own phone-card fallback keeps this readable narrow too).
 */
import { useEffect, useMemo, useState } from 'react';
import { Copy, FileJson, X } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Input, Select } from '../rj-ui/Field';
import { Badge, type RjBadgeProps } from '../rj-ui/Badge';
import { KpiCard } from '../rj-ui/KpiCard';
import { Table, type TableColumn } from '../rj-ui/Table';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';
import { CustomerByPhoneLookup, type FoundCustomer } from './CustomerByPhoneLookup';

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

/** Named presets, never a raw number a non-technical operator has to interpret. `''` means no
 *  time bound at all — the honest "الكل" the ten-day retention already caps for us. */
const HOUR_PRESETS: { value: string; label: string }[] = [
  { value: '1', label: 'آخر ساعة' },
  { value: '6', label: 'آخر 6 ساعات' },
  { value: '24', label: 'آخر 24 ساعة' },
  { value: '72', label: 'آخر 3 أيام' },
  { value: '240', label: 'آخر 10 أيام (الكل المحفوظ)' },
  { value: '', label: 'بلا حد زمني' },
];

type Tone = NonNullable<RjBadgeProps['tone']>;

/** A tone per severity, so the eye sorts the list before the reader does. An unknown severity —
 *  and there WILL be unknown severities, that is the whole point of the free-form column — gets
 *  the neutral tone rather than being hidden or crashing the row. */
function severityTone(severity: string): Tone {
  const s = severity.toLowerCase();
  if (s === 'error' || s === 'fatal' || s === 'critical') return 'danger';
  if (s === 'warning' || s === 'warn') return 'warning';
  if (s === 'info' || s === 'debug') return 'info';
  return 'neutral';
}

/** HTTP status, the same reading order anyone recognises from a browser devtools tab: 2xx calm,
 *  4xx a caller's own mistake, 5xx the platform's. Blank stays blank — a signal with no status
 *  code did not answer 0, and colouring "no status" as anything would claim it did. */
function statusTone(code: number | null): Tone {
  if (code == null) return 'neutral';
  if (code >= 500) return 'danger';
  if (code >= 400) return 'warning';
  return 'success';
}

/** DETERMINISTIC, NOT ARBITRARY — the same string always lands on the same tone, so a `source` or
 *  `service` column stays visually stable across reloads instead of reshuffling colours on every
 *  page. Both columns are free-form (the collector's own design, see the module docstring), so a
 *  fixed lookup table would miss the next value that shows up; a hash over a small distinct palette
 *  gives real, useful colour separation without ever needing a release for a new one. Excludes
 *  danger/warning — those stay reserved for severity/status so a reader never reads "this service
 *  is failing" out of a colour that only ever meant "this is service #3 alphabetically". */
const PALETTE: Tone[] = ['accent', 'success', 'info', 'neutral'];
function toneFromString(s: string): Tone {
  let h = 0;
  for (let i = 0; i < s.length; i += 1) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return PALETTE[h % PALETTE.length];
}

function whenText(epochSeconds: number): string {
  if (!epochSeconds) return '';
  return new Date(epochSeconds * 1000).toLocaleString('ar-SA-u-nu-latn');
}

/** ONE ROW AS PLAIN TEXT — the short human-readable copy, next to the full-JSON copy per row. A
 *  support thread quoting either must not look like two different incidents. */
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
  // البحث بالعميل فعل منفصل (platform.operations لا platform.observability) — نفس الاستقلال
  // اللي AdminCompliance.tsx يطبّقه على فعل البحث حقّه، بنفس السبب بالضبط.
  const lookupAction = catalog.services.flatMap((s) => s.actions)
    .find((a) => a.id === 'operations.customer_by_phone');
  return <SignalsList session={session} action={listAction} lookupAction={lookupAction} />;
}

function SignalsList({ session, action, lookupAction }: {
  session: AdminSession; action: AdminAction; lookupAction: AdminAction | undefined;
}) {
  const [page, setPage] = useState<SignalsPage | 'loading' | 'failed'>('loading');
  // The filter lists persist across reloads: narrowing to one source must not make every OTHER
  // option vanish, which is what happens if the options are read from the current page alone.
  const [known, setKnown] = useState<{ sources: string[]; severities: string[]; services: string[] }>(
    { sources: [], severities: [], services: [] });

  const [sources, setSources] = useState<string[]>([]);
  const [severities, setSeverities] = useState<string[]>([]);
  const [service, setService] = useState('');
  const [hours, setHours] = useState('24');
  const [q, setQ] = useState('');
  const [customer, setCustomer] = useState<FoundCustomer | null>(null);
  const [copied, setCopied] = useState('');

  async function search() {
    setPage('loading');
    const params = new URLSearchParams();
    for (const s of sources) params.append('source', s);
    for (const s of severities) params.append('severity', s);
    if (service) params.set('service', service);
    if (hours) {
      params.set('since', String(Math.floor(Date.now() / 1000) - Math.floor(Number(hours) * 3600)));
    }
    if (q.trim()) params.set('q', q.trim());
    // العميل الموجود يُصفّي مباشرة على منشأته وهويّته المستعارة — لا على رقم جواله (لا يغادر
    // هذا الملف قط)، نفس انضباط subject_ref في AdminCompliance.tsx.
    if (customer) {
      params.set('tenant', customer.tenant);
      if (customer.subject_ref) params.set('subject_ref', customer.subject_ref);
    }
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

  // أول تحميل بلا أي فلتر — كل الأخطاء. والخدمة/المدة/العميل تُعيد البحث فوراً عند تغييرها، بلا
  // ضغط زر — راجع تعليق الملف عن «الصفحة تفرض عليه الحفظ». الشدّة/المصدر/النص يبقون يحتاجون «بحث».
  // eslint-disable-next-line react-hooks/exhaustive-deps -- search() itself is stable per its own closures
  useEffect(() => { search(); }, [service, hours, customer?.tenant, customer?.subject_ref]);

  const rows = page === 'loading' || page === 'failed' ? [] : page.signals;

  const counts = useMemo(() => ({
    total: rows.length,
    danger: rows.filter((r) => severityTone(r.severity) === 'danger').length,
    warning: rows.filter((r) => severityTone(r.severity) === 'warning').length,
    info: rows.filter((r) => severityTone(r.severity) === 'info').length,
  }), [rows]);

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

  const columns: TableColumn<Signal>[] = [
    { key: 'time', header: 'الوقت',
      render: (s) => <span dir="ltr" className="text-label text-text-secondary">{whenText(s.received_at)}</span> },
    { key: 'severity', header: 'الشدّة',
      render: (s) => <Badge tone={severityTone(s.severity)}>{s.severity || '—'}</Badge> },
    { key: 'source', header: 'المصدر', hideOnCard: true,
      render: (s) => <Badge tone={toneFromString(s.source)}>{s.source || '—'}</Badge> },
    { key: 'service', header: 'الخدمة',
      render: (s) => <Badge tone={toneFromString(s.service)}>{s.service || '—'}</Badge> },
    { key: 'status', header: 'الحالة', hideOnCard: true,
      render: (s) => s.status_code != null
        ? <Badge tone={statusTone(s.status_code)} dir="ltr">HTTP {s.status_code}</Badge>
        : <span className="text-text-muted">—</span> },
    { key: 'message', header: 'الرسالة', className: 'max-w-[28rem]',
      render: (s) => <span dir="ltr" className="block whitespace-pre-wrap break-words text-sm">{s.message}</span> },
    { key: 'actions', header: 'نسخ',
      render: (s) => (
        <div className="flex items-center gap-1">
          <Button type="button" size="icon" variant="ghost" aria-label="نسخ كنص"
                  onClick={() => copy(signalToText(s), 'نُسخ')}>
            <Copy size={14} />
          </Button>
          <Button type="button" size="icon" variant="ghost" aria-label="نسخ JSON كامل"
                  onClick={() => copy(JSON.stringify(s, null, 2), 'نُسخ JSON')}>
            <FileJson size={14} />
          </Button>
        </div>
      ) },
  ];

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">سجل الأخطاء</h1>
      <p className="text-sm text-text-secondary">
        كل خطأ سجّلته المنصة — من خوادمها ومن متصفحات المستخدمين — في مكان واحد. يُحفظ عشرة أيام
        ثم يُمحى تلقائياً.
      </p>

      {/* بطاقات ملخّص ملوَّنة — نفس نمط KpiCard المستخدم بشاشات الحالة الثانية، لا أرقام عادية
         بلا لون. الأرقام عن الصفحة المعروضة حالياً (حتى 200 صف)، لا عن كامل السجل — عنوان كل
         بطاقة يقول ذلك صراحة. */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <KpiCard tone="accent" label="إجمالي المعروض" value={counts.total}
                icon={<FileJson size={18} />} testId="kpi-total" />
        <KpiCard tone="danger" label="أخطاء" value={counts.danger}
                icon={<X size={18} />} testId="kpi-danger" />
        <KpiCard tone="warning" label="تحذيرات" value={counts.warning}
                icon={<X size={18} />} testId="kpi-warning" />
        <KpiCard tone="info" label="معلومات" value={counts.info}
                icon={<X size={18} />} testId="kpi-info" />
      </div>

      {lookupAction ? (
        <CustomerByPhoneLookup session={session} action={lookupAction} onFound={setCustomer}
                               foundNote="الجدول أدناه مصفّى الآن على أخطاء هذا العميل بالذات." />
      ) : null}
      {customer ? (
        <div className="flex items-center gap-2 text-sm">
          <span className="text-text-secondary">مصفّى على عميل واحد.</span>
          <Button type="button" size="sm" variant="ghost" onClick={() => setCustomer(null)}>
            <X size={14} /> إلغاء التصفية
          </Button>
        </div>
      ) : null}

      <form className="flex flex-col gap-4" onSubmit={(e) => { e.preventDefault(); setCopied(''); search(); }}>
        <CheckboxRow label="المصدر" options={known.sources} selected={sources} onChange={setSources} />
        <CheckboxRow label="الشدّة" options={known.severities} selected={severities} onChange={setSeverities} />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          <label className="flex flex-col gap-1">
            <span className="text-label font-medium text-text-secondary">الخدمة</span>
            {/* اختيار من قائمة، لا كتابة — كتابة اسم خدمة بجانب جدول أسمائها الحقيقية كانت تدعو
               لخطأ إملائي يرجع صفراً بصمت. */}
            <Select dir="ltr" value={service} onChange={(e) => setService(e.target.value)}>
              <option value="">كل الخدمات</option>
              {known.services.map((s) => <option key={s} value={s}>{s}</option>)}
            </Select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-label font-medium text-text-secondary">آخر كم مدة</span>
            <Select dir="ltr" value={hours} onChange={(e) => setHours(e.target.value)}>
              {HOUR_PRESETS.map((h) => <option key={h.value} value={h.value}>{h.label}</option>)}
            </Select>
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
            نسخ الكل نصاً
          </Button>
          {copied ? <span className="text-label text-success">{copied}</span> : null}
        </div>
      </form>

      <Table columns={columns} rows={page === 'failed' ? 'failed' : page === 'loading' ? 'loading' : rows}
            getRowId={(s) => s.id}
            emptyTitle="لا أخطاء بهذي الفلاتر"
            failedTitle="تعذّرت قراءة سجل الأخطاء" />
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
