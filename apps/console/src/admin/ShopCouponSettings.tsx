/**
 * إعدادات «تحالف استراتيجي» (اسم الواجهة لما كان يُسمّى «كوبونات محل لمحل» بالكود — الملفات
 * والمسارات لم تُعَد تسميتها) — السقف العام، الشرائح التلقائية، وسقف خاص لمحل معيّن، مبنية كشاشة
 * مخصّصة لأن العارض العام (ActionRenderer.tsx) لا يعرض حقلاً قائمة (الشرائح) ولا يوفّر أداة بحث
 * عن محل — راجع core/coupons.py لتفاصيل المحرك نفسه.
 *
 * غير قسم «الخصومات والعروض» (CouponCards.tsx) عمداً — ذاك يدير أكواد خصم فردية في billing-
 * service، وهذا يدير محرّكاً مختلفاً كلياً (امتياز محل على اشتراك محل آخر). نفس الكلمة «كوبون»
 * بالكود، مفهومان مختلفان تمامًا للمستخدم، فلهذا قسم فرعي خاص باسم مختلف يوضّح الفرق.
 */
import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input } from '../rj-ui/Field';
import { EmptyState } from '../rj-ui/EmptyState';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';
import { sentenceFor } from '../api';

interface Tier { max_grants: number; percent: number }
interface Settings { ceiling_percent: number; base_percent: number; tiers: Tier[] }

export function ShopCouponSettings({ session, settingsGetAction, settingsSetAction,
  lookupAction, overrideGetAction, overrideSetAction }: {
  session: AdminSession;
  settingsGetAction?: AdminAction; settingsSetAction?: AdminAction;
  lookupAction?: AdminAction; overrideGetAction?: AdminAction; overrideSetAction?: AdminAction;
}) {
  if (!settingsGetAction) {
    return <EmptyState title="حسابك لا يحمل صلاحية القراءة هنا." />;
  }
  return (
    <div className="flex flex-col gap-6">
      <GlobalSettingsCard session={session} getAction={settingsGetAction} setAction={settingsSetAction} />
      {lookupAction && overrideGetAction ? (
        <TenantOverrideCard session={session} lookupAction={lookupAction}
                           overrideGetAction={overrideGetAction} overrideSetAction={overrideSetAction} />
      ) : null}
    </div>
  );
}

function GlobalSettingsCard({ session, getAction, setAction }: {
  session: AdminSession; getAction: AdminAction; setAction?: AdminAction;
}) {
  const [settings, setSettings] = useState<Settings | 'loading' | 'failed'>('loading');
  const [ceiling, setCeiling] = useState('35');
  const [base, setBase] = useState('10');
  const [tiers, setTiers] = useState<Tier[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    req<Settings>(getAction.path, 'GET', undefined, session.access_token)
      .then((s) => {
        setSettings(s);
        setCeiling(String(s.ceiling_percent));
        setBase(String(s.base_percent));
        setTiers(s.tiers);
      })
      .catch(() => setSettings('failed'));
  }, [getAction, session]);

  function addTier() {
    setTiers((t) => [...t, { max_grants: 0, percent: 0 }]);
  }
  function removeTier(i: number) {
    setTiers((t) => t.filter((_, idx) => idx !== i));
  }
  function updateTier(i: number, field: keyof Tier, value: string) {
    const n = Number(value);
    if (Number.isNaN(n)) return;
    setTiers((t) => t.map((row, idx) => (idx === i ? { ...row, [field]: n } : row)));
  }

  async function save() {
    if (!setAction) return;
    const ceilingN = Number(ceiling);
    const baseN = Number(base);
    if (!Number.isInteger(ceilingN) || ceilingN <= 0 || ceilingN > 100) {
      setError('السقف العام يجب أن يكون بين 1 و100.'); return;
    }
    if (!Number.isInteger(baseN) || baseN < 0 || baseN > ceilingN) {
      setError('النسبة الافتراضية يجب ألا تتجاوز السقف العام.'); return;
    }
    setBusy(true); setError(''); setSaved(false);
    try {
      const s = await req<Settings>(setAction.path, 'PATCH',
        { ceiling_percent: ceilingN, base_percent: baseN, tiers }, session.access_token);
      setSettings(s); setTiers(s.tiers);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ الإعدادات.'));
    } finally {
      setBusy(false);
    }
  }

  if (settings === 'loading') return <p className="text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (settings === 'failed') return <p role="alert" className="text-danger text-sm">تعذّرت قراءة الإعدادات.</p>;

  return (
    <section className="flex flex-col gap-4 rounded-card border border-border-subtle bg-surface-1 p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-bold">السقف العام والشرائح التلقائية</h2>
        <p className="text-sm text-text-secondary">
          السقف العام هو الحاجز الأخير — ولا محل يتجاوزه بأي حال، حتى لو رُفع سقفه الخاص.
        </p>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Field label="السقف العام (%)" htmlFor="ceiling-percent"
              hint="أقصى نسبة خصم يمكن لأي محل منحها إطلاقاً">
          <Input id="ceiling-percent" dir="ltr" inputMode="numeric" value={ceiling}
                onChange={(e) => setCeiling(e.target.value)} disabled={!setAction} />
        </Field>
        <Field label="النسبة الافتراضية (%)" htmlFor="base-percent"
              hint="لمحل بلا سجل نشاط بعد، ولا شرائح مُعرَّفة">
          <Input id="base-percent" dir="ltr" inputMode="numeric" value={base}
                onChange={(e) => setBase(e.target.value)} disabled={!setAction} />
        </Field>
      </div>

      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">الشرائح</span>
          {setAction ? (
            <Button type="button" size="sm" variant="outline" onClick={addTier}>+ شريحة جديدة</Button>
          ) : null}
        </div>
        <p className="text-xs text-text-secondary">
          محل منح عدد خصومات الشهر الماضي أقل من أو يساوي «عدد الخصومات» هنا يأخذ «النسبة»
          المقابلة، الشهر التالي.
        </p>
        {tiers.length === 0 ? (
          <p className="text-sm text-text-secondary">لا شرائح مُعرَّفة — كل محل يأخذ النسبة الافتراضية.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {tiers.map((tier, i) => (
              <li key={i} className="flex items-center gap-2">
                <Input dir="ltr" inputMode="numeric" value={String(tier.max_grants)}
                      onChange={(e) => updateTier(i, 'max_grants', e.target.value)}
                      disabled={!setAction} className="w-24" aria-label="عدد الخصومات" />
                <span className="text-sm text-text-secondary">خصم أو أقل ←</span>
                <Input dir="ltr" inputMode="numeric" value={String(tier.percent)}
                      onChange={(e) => updateTier(i, 'percent', e.target.value)}
                      disabled={!setAction} className="w-20" aria-label="النسبة" />
                <span className="text-sm text-text-secondary">%</span>
                {setAction ? (
                  <Button type="button" size="sm" variant="ghost" className="text-danger"
                          onClick={() => removeTier(i)}>حذف</Button>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>

      {setAction ? (
        <div className="flex items-center gap-3">
          <Button type="button" disabled={busy} onClick={save}>
            {busy ? 'جارٍ الحفظ…' : 'حفظ الإعدادات'}
          </Button>
          {saved ? <span className="text-sm text-success">✓ تم الحفظ</span> : null}
        </div>
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </section>
  );
}

function TenantOverrideCard({ session, lookupAction, overrideGetAction, overrideSetAction }: {
  session: AdminSession; lookupAction: AdminAction; overrideGetAction: AdminAction;
  overrideSetAction?: AdminAction;
}) {
  const [phone, setPhone] = useState('');
  const [searching, setSearching] = useState(false);
  const [tenant, setTenant] = useState('');
  const [notFound, setNotFound] = useState(false);
  const [override, setOverride] = useState<{ percent: number | null; note: string } | null>(null);
  const [percentText, setPercentText] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  async function search() {
    if (!phone.trim()) return;
    setSearching(true); setError(''); setTenant(''); setNotFound(false); setOverride(null);
    try {
      const r = await req<{ tenant: string }>(
        `${lookupAction.path}?phone=${encodeURIComponent(phone.trim())}`,
        'GET', undefined, session.access_token);
      if (!r.tenant) { setNotFound(true); return; }
      setTenant(r.tenant);
      const o = await req<{ percent: number | null; note: string }>(
        overrideGetAction.path.replace('{tenant_id}', encodeURIComponent(r.tenant)),
        'GET', undefined, session.access_token);
      setOverride(o);
      setPercentText(o.percent === null ? '' : String(o.percent));
      setNote(o.note);
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر البحث.'));
    } finally {
      setSearching(false);
    }
  }

  async function save(clear: boolean) {
    if (!overrideSetAction || !tenant) return;
    const percent = clear || !percentText.trim() ? null : Number(percentText);
    if (percent !== null && (!Number.isInteger(percent) || percent < 0 || percent > 100)) {
      setError('النسبة يجب أن تكون بين 0 و100.'); return;
    }
    setBusy(true); setError(''); setSaved(false);
    try {
      const o = await req<{ percent: number | null; note: string }>(
        overrideSetAction.path.replace('{tenant_id}', encodeURIComponent(tenant)),
        'PATCH', { tenant, percent, note: clear ? '' : note }, session.access_token);
      setOverride(o);
      setPercentText(o.percent === null ? '' : String(o.percent));
      setNote(o.note);
      setSaved(true);
      window.setTimeout(() => setSaved(false), 2000);
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ السقف الخاص — تأكد أنه لا يتجاوز السقف العام.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="flex flex-col gap-4 rounded-card border border-border-subtle bg-surface-1 p-5 shadow-sm">
      <div>
        <h2 className="text-lg font-bold">سقف خاص لمحل معيّن</h2>
        <p className="text-sm text-text-secondary">
          ميزة تنافسية — ارفع سقف محل مكافأةً له، أو امسح الاستثناء ليرجع لسقفه التلقائي. نفس رقم
          الجوال الذي سجّل به المحل عندنا.
        </p>
      </div>

      <div className="flex items-end gap-2">
        <Field label="رقم جوال المحل" htmlFor="tenant-phone" className="flex-1">
          <Input id="tenant-phone" dir="ltr" value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder="05xxxxxxxx" />
        </Field>
        <Button type="button" disabled={searching || !phone.trim()} onClick={search}
               className="flex items-center gap-2">
          <Search size={14} /> {searching ? 'جارٍ البحث…' : 'بحث'}
        </Button>
      </div>

      {notFound ? (
        <p className="text-sm text-danger">لا يوجد محل مسجّل بهذا الرقم.</p>
      ) : null}

      {tenant && override ? (
        <div className="flex flex-col gap-3 border-t border-border-subtle pt-4">
          <p className="text-xs text-text-tertiary" dir="ltr">{tenant}</p>
          <div className="grid grid-cols-2 gap-3">
            <Field label="السقف الخاص (%)" htmlFor="override-percent" hint="فارغ = بلا استثناء، يتبع الشرائح">
              <Input id="override-percent" dir="ltr" inputMode="numeric" value={percentText}
                    onChange={(e) => setPercentText(e.target.value)} disabled={!overrideSetAction} />
            </Field>
            <Field label="ملاحظة" htmlFor="override-note">
              <Input id="override-note" value={note} onChange={(e) => setNote(e.target.value)}
                    disabled={!overrideSetAction} />
            </Field>
          </div>
          {overrideSetAction ? (
            <div className="flex items-center gap-3">
              <Button type="button" disabled={busy} onClick={() => save(false)}>
                {busy ? 'جارٍ الحفظ…' : 'حفظ'}
              </Button>
              {override.percent !== null ? (
                <Button type="button" variant="outline" disabled={busy} onClick={() => save(true)}>
                  مسح الاستثناء
                </Button>
              ) : null}
              {saved ? <span className="text-sm text-success">✓ تم الحفظ</span> : null}
            </div>
          ) : null}
        </div>
      ) : null}

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
    </section>
  );
}
