/**
 * نجاح العملاء — تبويب بشاشة "العملاء والدعم" الرئيسية، مستوى المنصة كلها لا محل واحد: يجيب كل
 * المستأجرين (`tenant.list`، نفس مسار CustomerList.tsx) ثم يسأل operations سؤالين حقيقيين عن كل
 * واحد (`operations.customer_success_scan`): هل مرّت مدة التعثّر بلا ما يضيف خدمة، وهل عنده خدمات
 * بس ولا زيارة سُجّلت له أبداً — من سجلّات الخدمة/الزيارة الفعلية، لا تخمين ولا رقم مُلفَّق.
 *
 * المدّة (كم يوم تُعتبر «تعثّر») اختيار حقيقي بالشاشة، لا رقم مثبّت بالكود — العملية دائماً واضحة:
 * الفريق يقرر بنفسه أي نافذة تناسبه اليوم، ويقدر يوسّعها أو يضيّقها بلا أي تعديل كود.
 */
import { useEffect, useState } from 'react';
import { AlertTriangle, PackageX, RefreshCw, TrendingUp } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { KpiCard } from '../rj-ui/KpiCard';
import { Select } from '../rj-ui/Field';
import { Table, type TableColumn } from '../rj-ui/Table';
import { allActions, fetchCatalog, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';
import type { Tenant } from './CustomerList';

interface StallingRow {
  tenant: string; name: string;
  no_services_after_stall: boolean; has_services_no_visits: boolean;
}

const STALL_PRESETS = [1, 3, 7, 14];

export function CustomerSuccess({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [stallDays, setStallDays] = useState(3);
  const [rows, setRows] = useState<StallingRow[] | 'loading' | 'failed' | 'idle'>('idle');
  const [scanned, setScanned] = useState(0);

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  const listAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'tenant.list') : undefined;
  const scanAction = catalog !== 'loading' && catalog !== 'failed'
    ? allActions(catalog).find((a) => a.id === 'operations.customer_success_scan') : undefined;

  async function scan() {
    if (!listAction || !scanAction) return;
    setRows('loading');
    try {
      const { tenants } = await req<{ tenants: Tenant[] }>(
        listAction.path, 'GET', undefined, session.access_token);
      const body = await req<{ stalling: StallingRow[]; scanned: number }>(
        scanAction.path, 'POST',
        { tenants: tenants.map((t) => ({ id: t.id, name: t.name, created_at: t.created_at })),
         stall_days: stallDays },
        session.access_token);
      setRows(body.stalling);
      setScanned(body.scanned);
    } catch {
      setRows('failed');
    }
  }

  // eslint-disable-next-line react-hooks/exhaustive-deps -- scan itself is stable per its own closures; re-fires on stallDays change
  useEffect(() => { if (listAction && scanAction) scan(); }, [listAction, scanAction, stallDays]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;
  if (!listAction || !scanAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;
  }

  const shown = rows === 'loading' || rows === 'failed' || rows === 'idle' ? [] : rows;
  const noServices = shown.filter((r) => r.no_services_after_stall);
  const noVisits = shown.filter((r) => r.has_services_no_visits);

  const columns: TableColumn<StallingRow>[] = [
    { key: 'name', header: 'المحل', render: (r) => <span className="font-medium">{r.name || r.tenant}</span> },
    { key: 'reason', header: 'سبب التعثّر', render: (r) => (
      r.no_services_after_stall ? (
        <Badge tone="danger"><PackageX size={12} /> بلا خدمات منذ التسجيل</Badge>
      ) : (
        <Badge tone="warning"><AlertTriangle size={12} /> بلا زيارات مسجَّلة</Badge>
      )
    ) },
  ];

  return (
    <div className="flex flex-col gap-5 p-6">
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <KpiCard icon={<TrendingUp size={18} />} label="محلات متعثّرة" value={shown.length}
                tone={shown.length > 0 ? 'danger' : 'success'} testId="kpi-stalling-total" />
        <KpiCard icon={<PackageX size={18} />} label="بلا خدمات منذ التسجيل" value={noServices.length}
                tone={noServices.length > 0 ? 'danger' : 'neutral'} />
        <KpiCard icon={<AlertTriangle size={18} />} label="بلا زيارات مسجَّلة" value={noVisits.length}
                tone={noVisits.length > 0 ? 'warning' : 'neutral'} />
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-text-secondary">تعثّر التسجيل بعد</span>
          <Select dir="ltr" value={String(stallDays)}
                 onChange={(e) => setStallDays(Number(e.target.value))} className="w-auto">
            {STALL_PRESETS.map((d) => <option key={d} value={d}>{d} {d === 1 ? 'يوم' : 'أيام'}</option>)}
          </Select>
        </label>
        <Button variant="outline" size="sm" onClick={scan} disabled={rows === 'loading'}>
          <RefreshCw size={14} /> تحديث
        </Button>
        {rows !== 'loading' && rows !== 'idle' && rows !== 'failed' ? (
          <span className="text-label text-text-muted">من أصل {scanned} محل</span>
        ) : null}
      </div>

      <Table columns={columns} rows={rows === 'idle' ? 'loading' : rows === 'failed' ? 'failed' : shown}
            getRowId={(r) => r.tenant}
            emptyTitle="لا محلات متعثّرة بهذي المدّة — الوضع سليم"
            failedTitle="تعذّر فحص المحلات المتعثّرة" />
    </div>
  );
}
