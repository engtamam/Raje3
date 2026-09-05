/**
 * المالية — القسم 4. مبنية يدوياً: `billing.platform_invoices`/`billing.platform_subscriptions`
 * ترفض بلا فلتر واحد على الأقل (لا مسح غير مفلتَر عبر كل العملاء)، والتسوية/العكس/الاسترجاع
 * حقول إلزامية مركّبة — لا يلائم أياً منها زر "قائمة" واحد بالمحرّك العام.
 *
 * النموذج التجاري: مسبوق الدفع بالكامل — مدفوعة أو غير مدفوعة، لا حالة "متأخرة". العروض
 * المحفوظة الثلاثة أدناه هي الأسئلة الحقيقية التي تُفتح الشاشة عليها، لا فلاتر عامة.
 */
import { useState } from 'react';
import { useEffect } from 'react';
import { Button } from '../rj-ui/Button';
import { Input, Select } from '../rj-ui/Field';
import { Segmented } from '../rj-ui/Segmented';
import { Badge } from '../rj-ui/Badge';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { Table, type TableColumn } from '../rj-ui/Table';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { sentenceFor } from '../api';
import { riyalsLabel, halalas } from '../money';
import { NoActionAvailable } from './NoActionAvailable';

type SubTab = 'invoices' | 'subscriptions' | 'tools';

export function AdminFinance({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [sub, setSub] = useState<SubTab>('invoices');

  useEffect(() => {
    let cancelled = false;
    fetchCatalog(session).then((c) => { if (!cancelled) setCatalog(c); })
      .catch(() => { if (!cancelled) setCatalog('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const actions = catalog.services.flatMap((s) => s.actions);
  const invoicesAction = actions.find((a) => a.id === 'billing.platform_invoices');
  const subscriptionsAction = actions.find((a) => a.id === 'billing.platform_subscriptions');
  const settleAction = actions.find((a) => a.id === 'billing.settle');
  const settlementsAction = actions.find((a) => a.id === 'billing.list_settlements');
  const reverseAction = actions.find((a) => a.id === 'billing.reverse_settlement');
  const refundAction = actions.find((a) => a.id === 'billing.refund');
  const reconcileAction = actions.find((a) => a.id === 'billing.reconcile_payment');

  if (!invoicesAction && !subscriptionsAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لعرض المالية." />;
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="px-6 pt-6">
        <h1 className="mb-3 text-2xl leading-tight tracking-tight">المالية</h1>
        <Segmented
          value={sub}
          onChange={(v) => setSub(v as SubTab)}
          options={[
            { value: 'invoices', label: 'الفواتير' },
            { value: 'subscriptions', label: 'الاشتراكات' },
            { value: 'tools', label: 'أدوات الدفع' },
          ]}
        />
      </div>
      {sub === 'invoices' && invoicesAction ? (
        <InvoicesPanel session={session} action={invoicesAction} settleAction={settleAction}
                      settlementsAction={settlementsAction} reverseAction={reverseAction} />
      ) : null}
      {sub === 'subscriptions' && subscriptionsAction ? (
        <SubscriptionsPanel session={session} action={subscriptionsAction} />
      ) : null}
      {sub === 'tools' ? (
        <PaymentTools session={session} refundAction={refundAction} reconcileAction={reconcileAction} catalog={catalog} />
      ) : null}
    </div>
  );
}

interface Invoice {
  id: string; tenant: string; number: string; subscription_id: string; status: string;
  subtotal_minor: number; tax_minor: number; total_minor: number; refunded_minor: number;
  currency: string; created: string; paid_at: string | null;
}

const TODAY = () => new Date().toISOString().slice(0, 10);
const MONTH_START = () => `${new Date().toISOString().slice(0, 7)}-01`;

function InvoicesPanel({ session, action, settleAction, settlementsAction, reverseAction }: {
  session: AdminSession; action: AdminAction;
  settleAction?: AdminAction; settlementsAction?: AdminAction; reverseAction?: AdminAction;
}) {
  const [status, setStatus] = useState('');
  const [tenant, setTenant] = useState('');
  const [since, setSince] = useState('');
  const [until, setUntil] = useState('');
  const [rows, setRows] = useState<Invoice[] | 'idle' | 'loading' | 'failed'>('idle');
  const [error, setError] = useState('');
  // AT MOST ONE OF THESE THREE IS EVER NON-NULL — `Modal` (rj-ui) explicitly documents it does
  // NOT support stacking a second instance (no shared registry, both would bind Escape and
  // scroll-lock independently). Opening any one of the three closes the other two, so only a
  // single `ConfirmDialog`/`Modal` is ever mounted at once — see `open*` below.
  const [settleFor, setSettleFor] = useState<Invoice | null>(null);
  const [settlementsFor, setSettlementsFor] = useState<Invoice | null>(null);
  const [reverseFor, setReverseFor] = useState<Settlement | null>(null);

  function openSettle(inv: Invoice) { setSettlementsFor(null); setReverseFor(null); setSettleFor(inv); }
  function openSettlements(inv: Invoice) { setSettleFor(null); setReverseFor(null); setSettlementsFor(inv); }
  function openReverse(s: Settlement) { setSettleFor(null); setSettlementsFor(null); setReverseFor(s); }

  async function search(overrides?: Partial<{ status: string; tenant: string; since: string; until: string }>) {
    const f = { status, tenant, since, until, ...overrides };
    if (!f.status && !f.tenant && !f.since && !f.until) {
      setError('فلتر واحد على الأقل مطلوب — لا مسح لكل الفواتير بلا فلتر.');
      return;
    }
    setError('');
    setRows('loading');
    const params = new URLSearchParams();
    if (f.status) params.set('status', f.status);
    if (f.tenant) params.set('tenant', f.tenant);
    if (f.since) params.set('since', f.since);
    if (f.until) params.set('until', f.until);
    try {
      const body = await req<{ invoices: Invoice[]; next_cursor: string | null }>(
        `${action.path}?${params.toString()}`, 'GET', undefined, session.access_token,
      );
      setRows(body.invoices);
    } catch (err) {
      setRows('failed');
      setError(sentenceFor(err, 'تعذّرت قراءة الفواتير.'));
    }
  }

  function savedView(next: { status: string; tenant: string; since: string; until: string }) {
    setStatus(next.status); setTenant(next.tenant); setSince(next.since); setUntil(next.until);
    search(next);
  }

  const columns: TableColumn<Invoice>[] = [
    { key: 'number', header: 'رقم الفاتورة' },
    { key: 'tenant', header: 'المحل' },
    { key: 'status', header: 'الحالة', render: (r) => <InvoiceStatusBadge status={r.status} /> },
    { key: 'total_minor', header: 'الإجمالي', render: (r) => riyalsLabel(r.total_minor) },
    { key: 'refunded_minor', header: 'المسترجَع', render: (r) => (r.refunded_minor ? riyalsLabel(r.refunded_minor) : '—'), hideOnCard: true },
    { key: 'created', header: 'التاريخ', render: (r) => new Date(r.created).toLocaleDateString('ar-SA') },
  ];
  if (settleAction) {
    columns.push({
      key: 'actions', header: '',
      render: (r) => (
        <div className="flex gap-1.5">
          <Button type="button" size="sm" variant="ghost" onClick={() => openSettle(r)}>تسوية</Button>
          {settlementsAction ? (
            <Button type="button" size="sm" variant="ghost" onClick={() => openSettlements(r)}>التسويات</Button>
          ) : null}
        </div>
      ),
    });
  }

  return (
    <div className="flex flex-col gap-4 px-6 pb-6">
      <div className="flex flex-wrap gap-2">
        <Button type="button" size="sm" variant="outline"
               onClick={() => savedView({ status: 'paid', tenant: '', since: TODAY(), until: '' })}>
          مدفوعات اليوم
        </Button>
        <Button type="button" size="sm" variant="outline"
               onClick={() => savedView({ status: 'open', tenant: '', since: '', until: '' })}>
          تجديدات لم تتم
        </Button>
        <Button type="button" size="sm" variant="outline"
               onClick={() => savedView({ status: 'void', tenant: '', since: MONTH_START(), until: '' })}>
          ملغاة هذا الشهر
        </Button>
      </div>

      <form className="grid grid-cols-2 gap-2 sm:grid-cols-4" onSubmit={(e) => { e.preventDefault(); search(); }}>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">الحالة</span>
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">— الكل —</option>
            <option value="open">غير مدفوعة</option>
            <option value="paid">مدفوعة</option>
            <option value="void">ملغاة</option>
            <option value="uncollectible">متعذّرة</option>
          </Select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">المحل</span>
          <Input dir="ltr" value={tenant} onChange={(e) => setTenant(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">منذ</span>
          <Input dir="ltr" type="date" value={since} onChange={(e) => setSince(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">حتى</span>
          <Input dir="ltr" type="date" value={until} onChange={(e) => setUntil(e.target.value)} />
        </label>
        <Button type="submit" className="col-span-2 sm:col-span-1">بحث</Button>
      </form>

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      <Table columns={columns} rows={rows === 'idle' ? [] : rows} getRowId={(r) => r.id}
            emptyTitle={rows === 'idle' ? 'اختر فلتراً أو عرضاً محفوظاً' : 'لا فواتير بهذي الفلاتر'}
            failedTitle="تعذّرت قراءة الفواتير" />

      {settleAction ? (
        <SettleDialog session={session} action={settleAction} invoice={settleFor}
                     onClose={() => setSettleFor(null)} onSettled={() => search()} />
      ) : null}
      {settlementsAction ? (
        <SettlementsDialog session={session} listAction={settlementsAction}
                           canReverse={Boolean(reverseAction)} invoice={settlementsFor}
                           onClose={() => setSettlementsFor(null)} onRequestReverse={openReverse} />
      ) : null}
      {reverseAction ? (
        <ReverseSettlementDialog session={session} action={reverseAction} settlement={reverseFor}
                                 onClose={() => setReverseFor(null)} />
      ) : null}
    </div>
  );
}

function InvoiceStatusBadge({ status }: { status: string }) {
  const tone = status === 'paid' ? 'success' : status === 'void' ? 'neutral'
    : status === 'uncollectible' ? 'danger' : 'warning';
  const label = { paid: 'مدفوعة', open: 'غير مدفوعة', void: 'ملغاة', uncollectible: 'متعذّرة' }[status] ?? status;
  return <Badge tone={tone}>{label}</Badge>;
}

function SettleDialog({ session, action, invoice, onClose, onSettled }: {
  session: AdminSession; action: AdminAction; invoice: Invoice | null;
  onClose: () => void; onSettled: () => void;
}) {
  const [method, setMethod] = useState('bank_transfer');
  const [issuer, setIssuer] = useState('');
  const [reference, setReference] = useState('');
  const [amount, setAmount] = useState('');
  const [paidAt, setPaidAt] = useState(TODAY());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (invoice) {
      setAmount((invoice.total_minor / 100).toFixed(2));
      setMethod('bank_transfer'); setIssuer(''); setReference(''); setPaidAt(TODAY()); setError('');
    }
  }, [invoice]);

  if (!invoice) return null;

  async function submit() {
    const amountMinor = halalas(amount);
    if (amountMinor === null || amountMinor <= 0 || !reference.trim()) return;
    setBusy(true);
    setError('');
    try {
      await req(action.path.replace('{invoice_id}', invoice!.id), 'POST', {
        method, issuer: issuer.trim(), reference: reference.trim(),
        amount_minor: amountMinor, paid_at: new Date(paidAt).getTime() / 1000,
      }, session.access_token);
      onSettled();
      onClose();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّرت التسوية.'));
    } finally {
      setBusy(false);
    }
  }

  // ONE Modal, not two — `submit` fires only once the operator types the invoice's own number
  // into `ConfirmDialog`'s built-in arm field (`confirmText`), the same single-dialog pattern
  // `AdminSecrets.tsx`/`PaymentTools` already use, instead of nesting a second `ConfirmDialog`
  // (which `rj-ui/Modal` documents it does not support stacking).
  return (
    <ConfirmDialog open onClose={onClose} onConfirm={submit} busy={busy} danger={false}
                  confirmLabel="تسجيل التسوية" confirmText={invoice.number}
                  title={`تسوية الفاتورة ${invoice.number}`}
                  body="سيُسجَّل هذا كدفع فعلي على الفاتورة — اكتب رقم الفاتورة للتأكيد.">
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">الطريقة</span>
          <Select value={method} onChange={(e) => setMethod(e.target.value)}>
            <option value="bank_transfer">حوالة بنكية</option>
            <option value="cheque">شيك</option>
          </Select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">البنك المُصدِر</span>
          <Input dir="ltr" value={issuer} onChange={(e) => setIssuer(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">رقم المرجع</span>
          <Input dir="ltr" value={reference} onChange={(e) => setReference(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">المبلغ (ريال)</span>
          <Input dir="ltr" value={amount} onChange={(e) => setAmount(e.target.value)} />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">تاريخ القيمة عند البنك</span>
          <Input dir="ltr" type="date" value={paidAt} onChange={(e) => setPaidAt(e.target.value)} />
        </label>
        {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      </div>
    </ConfirmDialog>
  );
}

interface Settlement {
  id: string; method: string; reference: string; amount_minor: number; paid_at: number;
}

function SettlementsDialog({ session, listAction, canReverse, invoice, onClose, onRequestReverse }: {
  session: AdminSession; listAction: AdminAction; canReverse: boolean;
  invoice: Invoice | null; onClose: () => void; onRequestReverse: (s: Settlement) => void;
}) {
  const [rows, setRows] = useState<Settlement[] | 'loading' | 'failed'>('loading');

  useEffect(() => {
    if (!invoice) return;
    setRows('loading');
    req<{ settlements: Settlement[] }>(
      listAction.path.replace('{invoice_id}', invoice.id), 'GET', undefined, session.access_token,
    ).then((b) => setRows(b.settlements)).catch(() => setRows('failed'));
  }, [invoice, listAction, session]);

  if (!invoice) return null;

  // ONE Modal — reversing a settlement opens a SEPARATE top-level dialog (`ReverseSettlementDialog`,
  // rendered by `InvoicesPanel`) instead of nesting a second `ConfirmDialog` here; `onRequestReverse`
  // closes this one first (see `openReverse` in `InvoicesPanel`).
  return (
    <ConfirmDialog open onClose={onClose} onConfirm={onClose}
                  title={`تسويات الفاتورة ${invoice.number}`} confirmLabel="إغلاق" danger={false}>
      {rows === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p> : null}
      {rows === 'failed' ? <p role="alert" className="text-danger text-sm">تعذّرت القراءة.</p> : null}
      {Array.isArray(rows) ? (
        rows.length === 0 ? (
          <p className="text-sm text-text-secondary">لا تسويات على هذي الفاتورة.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {rows.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center justify-between gap-2 rounded-input border border-border-subtle p-2 text-sm">
                <span className="min-w-0 break-words">{s.method} — {s.reference} — {riyalsLabel(s.amount_minor)}</span>
                {canReverse ? (
                  <Button type="button" size="sm" variant="ghost" onClick={() => onRequestReverse(s)}>عكس</Button>
                ) : null}
              </li>
            ))}
          </ul>
        )
      ) : null}
    </ConfirmDialog>
  );
}

function ReverseSettlementDialog({ session, action, settlement, onClose }: {
  session: AdminSession; action: AdminAction; settlement: Settlement | null; onClose: () => void;
}) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { if (settlement) { setReason(''); setError(''); } }, [settlement]);

  if (!settlement) return null;

  async function reverse() {
    if (!reason.trim()) return;
    setBusy(true);
    setError('');
    try {
      await req(action.path.replace('{settlement_id}', settlement!.id), 'POST',
                { reason: reason.trim(), actor: '' }, session.access_token);
      onClose();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر عكس التسوية.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <ConfirmDialog open onClose={onClose} onConfirm={reverse} busy={busy}
                  title={`عكس تسوية "${settlement.reference}"؟`}
                  body="سيُلغى أثرها على حالة الفاتورة، ولا تُحذف من السجلّ.">
      <label className="flex flex-col gap-1">
        <span className="text-label font-medium text-text-secondary">السبب</span>
        <Input dir="rtl" value={reason} onChange={(e) => setReason(e.target.value)} />
      </label>
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </ConfirmDialog>
  );
}

interface Subscription {
  id: string; tenant: string; plan_id: string; status: string; created: string; canceled_at: string | null;
}

function SubscriptionsPanel({ session, action }: { session: AdminSession; action: AdminAction }) {
  const [status, setStatus] = useState('');
  const [tenant, setTenant] = useState('');
  const [rows, setRows] = useState<Subscription[] | 'idle' | 'loading' | 'failed'>('idle');
  const [error, setError] = useState('');

  async function search() {
    if (!status && !tenant) {
      setError('فلتر واحد على الأقل مطلوب — الحالة أو المحل.');
      return;
    }
    setError('');
    setRows('loading');
    const params = new URLSearchParams();
    if (status) params.set('status', status);
    if (tenant) params.set('tenant', tenant);
    try {
      const body = await req<{ subscriptions: Subscription[] }>(
        `${action.path}?${params.toString()}`, 'GET', undefined, session.access_token,
      );
      setRows(body.subscriptions);
    } catch (err) {
      setRows('failed');
      setError(sentenceFor(err, 'تعذّرت قراءة الاشتراكات.'));
    }
  }

  const columns: TableColumn<Subscription>[] = [
    { key: 'tenant', header: 'المحل' },
    { key: 'plan_id', header: 'التطبيق' },
    { key: 'status', header: 'الحالة' },
    { key: 'created', header: 'بدأ', render: (r) => new Date(r.created).toLocaleDateString('ar-SA') },
    { key: 'canceled_at', header: 'انتهى', render: (r) => r.canceled_at ? new Date(r.canceled_at).toLocaleDateString('ar-SA') : '—' },
  ];

  return (
    <div className="flex flex-col gap-4 px-6 pb-6">
      <form className="grid grid-cols-2 gap-2 sm:grid-cols-3" onSubmit={(e) => { e.preventDefault(); search(); }}>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">الحالة</span>
          <Select value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">— الكل —</option>
            <option value="trialing">تجربة</option>
            <option value="active">فعّال</option>
            <option value="past_due">متأخر</option>
            <option value="paused">موقوف</option>
            <option value="canceled">ملغى</option>
          </Select>
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-label font-medium text-text-secondary">المحل</span>
          <Input dir="ltr" value={tenant} onChange={(e) => setTenant(e.target.value)} />
        </label>
        <Button type="submit" className="self-end">بحث</Button>
      </form>
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      <Table columns={columns} rows={rows === 'idle' ? [] : rows} getRowId={(r) => r.id}
            emptyTitle={rows === 'idle' ? 'اختر فلتراً' : 'لا اشتراكات بهذي الفلاتر'}
            failedTitle="تعذّرت قراءة الاشتراكات" />
    </div>
  );
}

function PaymentTools({ session, refundAction, reconcileAction, catalog }: {
  session: AdminSession; refundAction?: AdminAction; reconcileAction?: AdminAction;
  catalog: AdminCatalog;
}) {
  const [paymentId, setPaymentId] = useState('');
  const [armRefund, setArmRefund] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState('');
  const [error, setError] = useState('');

  async function refund() {
    if (!refundAction || !paymentId.trim()) return;
    setBusy(true);
    setError('');
    setResult('');
    try {
      const body = await req<{ ok: boolean; status?: string; reason?: string }>(
        refundAction.path.replace('{payment_id}', paymentId.trim()), 'POST', undefined, session.access_token,
      );
      setResult(body.ok ? `تم الاسترجاع — الحالة: ${body.status}` : `تعذّر: ${body.reason}`);
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر الاسترجاع.'));
    } finally {
      setBusy(false);
      setArmRefund(false);
    }
  }

  async function reconcile() {
    if (!reconcileAction || !paymentId.trim()) return;
    setBusy(true);
    setError('');
    setResult('');
    try {
      const body = await req<Record<string, unknown>>(
        reconcileAction.path.replace('{payment_id}', paymentId.trim()), 'POST', undefined, session.access_token,
      );
      setResult(JSON.stringify(body));
    } catch (err) {
      setError(sentenceFor(err, 'تعذّرت المطابقة مع البوابة.'));
    } finally {
      setBusy(false);
    }
  }

  if (!refundAction && !reconcileAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="لا صلاحية لديك لأدوات الدفع." />;
  }

  return (
    <div className="flex flex-col gap-4 px-6 pb-6">
      <p className="text-sm text-text-secondary">
        «دفعتُ ولم تُفتَح خدمتي؟» ابدأ بالمطابقة مع البوابة أولاً — التسوية اليدوية آخر الخيارات لا أولها.
      </p>
      <label className="flex flex-col gap-1 max-w-sm">
        <span className="text-label font-medium text-text-secondary">معرّف الدفعة (payment_id)</span>
        <Input dir="ltr" value={paymentId} onChange={(e) => setPaymentId(e.target.value)} />
      </label>
      <div className="flex gap-2">
        {reconcileAction ? (
          <Button type="button" disabled={!paymentId.trim() || busy} onClick={reconcile}>
            مطابقة مع البوابة
          </Button>
        ) : null}
        {refundAction ? (
          <Button type="button" variant="danger" disabled={!paymentId.trim() || busy}
                 onClick={() => setArmRefund(true)}>
            استرجاع كامل
          </Button>
        ) : null}
      </div>
      {result ? <p className="text-sm text-text-primary">{result}</p> : null}
      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}

      <ConfirmDialog open={armRefund} onClose={() => setArmRefund(false)} onConfirm={refund} busy={busy}
                    confirmText={paymentId.trim()} danger
                    title={`استرجاع الدفعة "${paymentId}" بالكامل؟`}
                    body="هذا يعكس المبلغ بالبوابة ويُلغي الفاتورة تلقائياً إن غطّى كامل قيمتها." />
    </div>
  );
}
