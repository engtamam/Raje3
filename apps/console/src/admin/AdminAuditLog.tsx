/**
 * سجل التدقيق — بحث + تحقّق سلسلة الهاش. مبنية يدوياً: `audit.query` فلاترها كثيرة ومركّبة
 * (فترة زمنية + عدة حقول نصية معاً)، لا يلائمها زر "قائمة" واحد كما بالمحرّك العام.
 */
import { useEffect, useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Input } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { Table, type TableColumn } from '../rj-ui/Table';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';

interface AuditEvent {
  id: string; seq: number; ts: string; service: string; action: string;
  actor: string; resource: string; tenant: string; ip: string;
}
interface VerifyResult { ok: boolean; checked: number; first_bad_seq: number | null; reason?: string }

const COLUMNS: TableColumn<AuditEvent>[] = [
  { key: 'ts', header: 'الوقت', render: (r) => new Date(r.ts).toLocaleString('ar-SA') },
  { key: 'service', header: 'الخدمة' },
  { key: 'action', header: 'الإجراء' },
  { key: 'actor', header: 'الفاعل' },
  { key: 'resource', header: 'المورد', hideOnCard: true },
  { key: 'tenant', header: 'التينانت' },
];

export function AdminAuditLog({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const actions = catalog.services.flatMap((s) => s.actions);
  const queryAction = actions.find((a) => a.id === 'audit.query');
  const verifyAction = actions.find((a) => a.id === 'audit.verify');

  if (!queryAction) {
    return <p className="p-6 text-sm text-text-secondary">لا صلاحية لديك لتصفّح سجل التدقيق.</p>;
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">سجل التدقيق</h1>
      {verifyAction ? <VerifyChain session={session} action={verifyAction} /> : null}
      <AuditSearch session={session} action={queryAction} />
    </div>
  );
}

function VerifyChain({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [result, setResult] = useState<VerifyResult | 'loading' | null>(null);

  async function run() {
    setResult('loading');
    try {
      const body = await req<VerifyResult>(action.path, 'GET', undefined, session.access_token);
      setResult(body);
    } catch {
      setResult({ ok: false, checked: 0, first_bad_seq: null, reason: 'تعذّر الاتصال بالخدمة.' });
    }
  }

  return (
    <div className="flex flex-col gap-2 rounded-card border border-border-subtle bg-surface-1 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="font-medium">تحقّق سلامة السلسلة</span>
        <Button type="button" size="sm" disabled={result === 'loading'} onClick={run}>
          تحقّق الآن
        </Button>
      </div>
      {result && result !== 'loading' ? (
        <div className="flex items-center gap-2 text-sm">
          {result.ok ? (
            <Badge tone="success">سليمة — {result.checked} حدثاً فُحصت</Badge>
          ) : (
            <Badge tone="danger">
              مكسورة{result.first_bad_seq != null ? ` — عند التسلسل ${result.first_bad_seq}` : ''}
              {result.reason ? ` — ${result.reason}` : ''}
            </Badge>
          )}
        </div>
      ) : null}
    </div>
  );
}

function AuditSearch({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [filters, setFilters] = useState({ actor: '', action: '', service: '', resource: '', since: '', until: '' });
  const [events, setEvents] = useState<AuditEvent[] | 'loading' | 'failed'>('loading');

  async function search() {
    setEvents('loading');
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) {
      if (value.trim()) params.set(key, value.trim());
    }
    const qs = params.toString();
    try {
      const body = await req<{ events: AuditEvent[]; count: number }>(
        `${action.path}${qs ? `?${qs}` : ''}`, 'GET', undefined, session.access_token,
      );
      setEvents(body.events);
    } catch {
      setEvents('failed');
    }
  }

  useEffect(() => { search(); }, []); // eslint-disable-line react-hooks/exhaustive-deps -- first load, no filters yet

  return (
    <div className="flex flex-col gap-4">
      <form className="grid grid-cols-2 gap-2 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); search(); }}>
        <FilterField label="الفاعل" value={filters.actor} onChange={(v) => setFilters((p) => ({ ...p, actor: v }))} />
        <FilterField label="الإجراء" value={filters.action} onChange={(v) => setFilters((p) => ({ ...p, action: v }))} />
        <FilterField label="الخدمة" value={filters.service} onChange={(v) => setFilters((p) => ({ ...p, service: v }))} />
        <FilterField label="المورد" value={filters.resource} onChange={(v) => setFilters((p) => ({ ...p, resource: v }))} />
        <FilterField label="منذ" value={filters.since} onChange={(v) => setFilters((p) => ({ ...p, since: v }))} />
        <FilterField label="حتى" value={filters.until} onChange={(v) => setFilters((p) => ({ ...p, until: v }))} />
        <Button type="submit" className="col-span-2 sm:col-span-1">بحث</Button>
      </form>
      <Table columns={COLUMNS} rows={events} getRowId={(r) => r.id}
            emptyTitle="لا أحداث بهذي الفلاتر" failedTitle="تعذّرت قراءة سجل التدقيق" />
    </div>
  );
}

function FilterField({ label, value, onChange }: { label: string; value: string; onChange: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-label font-medium text-text-secondary">{label}</span>
      <Input dir="ltr" value={value} onChange={(e) => onChange(e.target.value)} />
    </label>
  );
}
