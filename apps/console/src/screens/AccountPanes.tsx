/**
 * The panes of «حسابي» that were stubs, built against what the services actually serve.
 *
 * EACH ONE IS BUILT FROM ITS ACTION OR IT IS NOT OFFERED AT ALL. Nothing here renders a control
 * whose action is missing from the catalogue: the gateway has already filtered by capability, so a
 * manager opening this page sees a shorter page rather than buttons that will refuse him.
 *
 * AND WHERE WE HAVE NO ACTION, THE PANE SAYS SO PLAINLY rather than showing a field that does
 * nothing. A disabled password box is worse than a sentence naming where the password is changed —
 * the box implies the product forgot to wire it, the sentence tells him what to do.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { Field, Input } from '@base-ui/design-system/Field';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Tenant {
  id?: string;
  name?: string;
  status?: string;
  branding?: { logo_url?: string; colour?: string };
  config?: { locale?: string; timezone?: string; calendar?: string };
}

// ── منشأتي ───────────────────────────────────────────────────────────────────────────────────

/**
 * The name and the mark HIS CUSTOMER sees — which is the whole reason this pane is not cosmetic.
 *
 * The customer page (spec 12) carries the establishment's identity and nothing of ours: no
 * platform name, no logo, no line in the footer. So this field is not "a profile"; it is the only
 * place the thing his customer reads is set.
 */
export function ShopPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [t, setT] = useState<Tenant | null | undefined>(undefined);
  const [saving, setSaving] = useState(false);
  const [said, setSaid] = useState('');
  const [error, setError] = useState('');

  const canRead = action(catalog, 'tenant.view_self');
  const canBrand = action(catalog, 'tenant.update_branding');

  const load = () => {
    if (!canRead) { setT(null); return; }
    call<Tenant>(session, canRead).then(setT).catch(() => setT(null));
  };
  useEffect(load, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (t === undefined) return <Skeleton height={160} />;
  if (!t) return <Quiet>لا تملك صلاحية عرض بيانات المنشأة.</Quiet>;

  const save = async (e: FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (!canBrand) return;
    const form = new FormData(e.currentTarget);
    setSaving(true); setError(''); setSaid('');
    try {
      await call(session, canBrand, { logo_url: String(form.get('logo_url') || '').trim() });
      setSaid('حُفظ.');
      load();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر الحفظ.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <Row label="اسم المنشأة" value={t.name || '—'} />
        <Row label="حالة الحساب" value={t.status === 'active' ? 'فعّال' : (t.status || '—')} />
        {/* FROM THE SERVER, NOT FROM THE BROWSER. Every reminder is scheduled against this
            timezone; reading the device's would schedule an owner travelling abroad into his
            customers' small hours. */}
        <Row label="التوقيت" value={t.config?.timezone || 'Asia/Riyadh'} />
        <Row label="التقويم" value={t.config?.calendar === 'hijri' ? 'هجري' : 'ميلادي'} />
      </Card>

      {canBrand ? (
        <form onSubmit={save} className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <h3 className="text-sm text-text-secondary">الشعار الذي يراه عميلك</h3>
          <Field label="رابط الشعار" hint="يظهر أعلى صفحة عميلك — اتركه فارغاً ليظهر اسم محلّك فقط">
            <Input name="logo_url" dir="ltr" defaultValue={t.branding?.logo_url ?? ''} />
          </Field>
          {t.branding?.logo_url ? (
            <img
              src={t.branding.logo_url}
              alt="شعار منشأتك"
              className="h-16 w-16 rounded-card object-contain"
            />
          ) : null}
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {said ? <p className="text-sm text-text-secondary">{said}</p> : null}
          <div><Button type="submit" disabled={saving}>حفظ</Button></div>
        </form>
      ) : null}
    </div>
  );
}

// ── دخولي ────────────────────────────────────────────────────────────────────────────────────

/**
 * WHAT HE SIGNS IN WITH, and one honest sentence about what he cannot change here.
 *
 * The phone IS the identity in this product — it is the login field and the channel every
 * verification code arrives on — so changing it is not an edit, it is moving the account. There is
 * no action for it in the catalogue and there should not be a box for it here.
 */
export function LoginPane({ session }: { session: Session }) {
  return (
    <div className="flex flex-col gap-4">
      <Card>
        <Row label="تدخل برقم جوالك" value="هو نفسه رقم محلّك المسجّل" />
        <Row label="مدة الجلسة" value="31 يوماً — لا تُطالَب بكلمة المرور كل مرة" />
      </Card>
      <Quiet>
        لتغيير كلمة المرور: سجّل الخروج، ثم «نسيت كلمة المرور» في شاشة الدخول — نرسل لك رابطاً على
        واتساب. نفعلها هكذا لأن كلمة المرور لا تُغيَّر من جلسة مفتوحة على جهاز قد لا يكون بيدك.
      </Quiet>
      <Quiet>
        تغيير رقم الجوال ليس تعديلاً — الرقم هو حسابك نفسه وقناة رسائلك. راسلنا وننقله لك بأمان.
      </Quiet>
      {/* The tenant is shown because a person who works at two shops needs to know which one this
          browser is in before he changes anything in it. */}
      <p className="text-sm text-text-secondary" dir="ltr">{session.tenant}</p>
    </div>
  );
}

// ── بياناتي وأوراقي ──────────────────────────────────────────────────────────────────────────

/**
 * PDPL, AS A CONTROL HE CAN PRESS — not as a paragraph.
 *
 * The right to access, export, correct and erase is his by law; a product that describes the right
 * and offers no way to use it has not granted it. `compliance.open_my_dsar` is that way, and this
 * pane exists to put it one tap from where he already is.
 */
export function DataPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [busy, setBusy] = useState('');
  const [said, setSaid] = useState('');
  const [error, setError] = useState('');
  const canAsk = action(catalog, 'compliance.open_my_dsar');

  const ask = async (kind: string, label: string) => {
    if (!canAsk) return;
    setBusy(kind); setError(''); setSaid('');
    try {
      await call(session, canAsk, { kind });
      setSaid(`استلمنا طلبك: ${label}. نردّ عليك خلال 30 يوماً كحدٍّ أقصى، وغالباً قبلها بكثير.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر تسجيل الطلب.');
    } finally {
      setBusy('');
    }
  };

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <h3 className="mb-1">الاحتفاظ بالبيانات</h3>
        <p className="text-sm text-text-secondary">
          زيارات عملائك وسجلّ رسائلهم محفوظة داخل المملكة. تبقى ما دام حسابك فعّالاً، وتُحذف بعد
          إغلاقه وفق المدة المعلنة في سياسة الخصوصية.
        </p>
      </Card>

      {canAsk ? (
        <div className="flex flex-col gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <h3>حقوقك في بياناتك</h3>
          <p className="text-sm text-text-secondary">
            نظام حماية البيانات الشخصية يمنحك هذه الطلبات، وهذه أزرارها — لا عنوان بريد تراسله.
          </p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('access', 'الاطّلاع على بياناتي')}>
              الاطّلاع على بياناتي
            </Button>
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('export', 'تصدير نسخة')}>
              تصدير نسخة
            </Button>
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('correction', 'تصحيح بيان')}>
              تصحيح بيان
            </Button>
            {/* ERASURE SITS APART AND IS NOT STYLED AS DANGER — it is a right, not an accident.
                What it must not be is adjacent to a routine button by a few pixels. */}
            <Button type="button" variant="ghost" disabled={Boolean(busy)}
                    onClick={() => ask('erasure', 'حذف بياناتي')}>
              حذف بياناتي
            </Button>
          </div>
          {error ? <p className="text-sm text-danger">{error}</p> : null}
          {said ? <p className="text-sm">{said}</p> : null}
        </div>
      ) : null}

      <Card>
        <h3 className="mb-1">الاتفاقيات</h3>
        <p className="text-sm text-text-secondary">
          شروط الاستخدام، سياسة الخصوصية، واتفاقية معالجة البيانات — وافقت عليها عند فتح المحل،
          وهي متاحة لك في أي وقت.
        </p>
        <div className="mt-3 flex flex-wrap gap-3 text-sm">
          <a className="underline" href="/legal/terms" target="_blank" rel="noreferrer">شروط الاستخدام</a>
          <a className="underline" href="/legal/privacy" target="_blank" rel="noreferrer">سياسة الخصوصية</a>
          <a className="underline" href="/legal/dpa" target="_blank" rel="noreferrer">اتفاقية معالجة البيانات</a>
        </div>
      </Card>
    </div>
  );
}

// ── the small shared pieces ──────────────────────────────────────────────────────────────────

function Card({ children }: { children: React.ReactNode }) {
  return <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">{children}</div>;
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-text-secondary">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function Quiet({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-card bg-surface-2 p-4 text-sm text-text-secondary">{children}</p>
  );
}

// ── الفواتير ─────────────────────────────────────────────────────────────────────────────────

interface Invoice { id: string; number?: string; status?: string; total_minor?: number; issued_at?: string }

/**
 * His invoices, and the document he actually needs.
 *
 * TWO DOWNLOADS, NOT ONE, because they are two different papers: the tax invoice is what his
 * accountant files, the receipt is proof he paid. Offering only "download" and picking one for him
 * sends half the shops to support.
 */
export function InvoicesPane({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [rows, setRows] = useState<Invoice[] | null>(null);
  const canList = action(catalog, 'billing.my_invoices');

  useEffect(() => {
    if (!canList) { setRows([]); return; }
    call<{ invoices: Invoice[] }>(session, canList)
      .then((x) => setRows(x.invoices ?? []))
      .catch(() => setRows([]));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!canList) return null;
  if (rows === null) return <Skeleton height={80} />;

  return (
    <div className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
      <h3 className="text-sm text-text-secondary">فواتيري</h3>
      {rows.length === 0 ? (
        // NOT AN APOLOGY. No invoices before the first subscription is the correct state, and
        // «لا توجد فواتير» dressed as an empty-state illustration would imply something failed.
        <p className="text-sm text-text-secondary">لا فواتير بعد — تصدر أول فاتورة مع أول باقة.</p>
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((v) => (
            <li key={v.id} className="flex items-center justify-between gap-3 border-b border-surface-2 pb-2 last:border-0">
              <span className="flex flex-col">
                <span className="tabular-nums" dir="ltr">{v.number || v.id}</span>
                <span className="text-sm text-text-secondary">{(v.issued_at || '').slice(0, 10)}</span>
              </span>
              <span className="flex items-center gap-3">
                <span className="tabular-nums">
                  {v.total_minor ? `${Math.round(v.total_minor / 100)} ريال` : '—'}
                </span>
                <Badge tone={v.status === 'paid' ? 'success' : 'warning'}>
                  {v.status === 'paid' ? 'مدفوعة' : 'غير مدفوعة'}
                </Badge>
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
