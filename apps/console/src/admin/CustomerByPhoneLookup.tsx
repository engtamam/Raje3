/**
 * بحث سريع عن عميل بمنشأة معروفة + رقم جواله — عنصر مشترك بين أكثر من شاشة إدارية (الامتثال،
 * سجل الأخطاء): موظف الدعم يعرف المحل الذي يخدمه العميل (لا بحث عبر كل المنشآت دفعة واحدة —
 * مطابقة تامة فقط، لا تخمين تقريبي)، فيكتب الاثنين ويحصل على ملفّه مباشرة، ثم كل شاشة تستعمل
 * النتيجة بطريقتها الخاصة (`onFound`) — استُخرج من AdminCompliance.tsx بعد ما احتاجته شاشة ثانية
 * بنفس الشكل تماماً، بدل تكرار نفس منطق البحث مرتين.
 */
import { useState } from 'react';
import { Search, User, XCircle } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Card } from '../rj-ui/Card';
import { Field, Input } from '../rj-ui/Field';
import type { AdminAction } from './catalog';
import { req, type AdminSession } from './api';

export interface FoundCustomer {
  id: string; tenant: string; phone: string; name: string;
  visit_count: number; last_visit: number;
  /** Only the platform admin route returns this (never the shop's own screen) — see
   *  operations/app/api/v1/platform.py's own note on why it is safe here specifically. */
  subject_ref?: string;
}

export function CustomerByPhoneLookup({ session, action, onFound, foundNote }: {
  session: AdminSession; action: AdminAction;
  onFound: (c: FoundCustomer | null) => void;
  /** A sentence explaining what finding a customer DOES on this particular screen — every caller
   *  uses the result differently, so the note belongs to the caller, not this shared box. */
  foundNote: string;
}) {
  const [tenant, setTenant] = useState('');
  const [phone, setPhone] = useState('');
  const [state, setState] = useState<'idle' | 'loading' | 'found' | 'missed' | 'failed'>('idle');
  const [result, setResult] = useState<FoundCustomer | null>(null);

  const search = async () => {
    if (!tenant.trim() || !phone.trim()) return;
    setState('loading'); setResult(null); onFound(null);
    try {
      const q = `?tenant=${encodeURIComponent(tenant.trim())}&phone=${encodeURIComponent(phone.trim())}`;
      const r = await req<{ customer: FoundCustomer | null }>(
        `${action.path}${q}`, 'GET', undefined, session.access_token);
      if (r.customer) { setResult(r.customer); setState('found'); onFound(r.customer); }
      else { setState('missed'); }
    } catch {
      setState('failed');
    }
  };

  return (
    <Card className="flex flex-col gap-3 p-4">
      <h2 className="font-medium">ابحث عن عميل</h2>
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <Field label="المنشأة (tenant)" className="flex-1">
          <Input value={tenant} onChange={(e) => setTenant(e.target.value)}
                placeholder="tnt_..." dir="ltr" />
        </Field>
        <Field label="رقم الجوال" className="flex-1">
          <Input value={phone} onChange={(e) => setPhone(e.target.value)}
                placeholder="05xxxxxxxx" dir="ltr"
                onKeyDown={(e) => { if (e.key === 'Enter') search(); }} />
        </Field>
        <Button onClick={search} disabled={state === 'loading' || !tenant.trim() || !phone.trim()}>
          <Search size={16} /> بحث
        </Button>
      </div>

      {state === 'failed' ? (
        <p role="alert" className="text-sm text-danger">تعذّر البحث. حاول مرة أخرى.</p>
      ) : null}
      {state === 'missed' ? (
        <p className="flex items-center gap-2 text-sm text-text-secondary">
          <XCircle size={16} className="shrink-0" /> لا عميل بهذا الرقم في هذه المنشأة.
        </p>
      ) : null}
      {state === 'found' && result ? (
        <div className="flex items-center gap-3 rounded-card bg-accent-soft p-3">
          <User size={20} className="shrink-0 text-accent-on-soft" />
          <div className="flex flex-col text-sm">
            <span className="font-medium">{result.name || 'بلا اسم مسجَّل'}</span>
            <span dir="ltr" className="text-text-secondary">{result.phone}</span>
            <span className="text-label text-text-secondary">
              {result.visit_count} زيارة — آخر زيارة{' '}
              {result.last_visit ? new Date(result.last_visit * 1000).toLocaleDateString('ar-SA-u-nu-latn') : '—'}
            </span>
            <span className="text-label text-accent-on-soft">{foundNote}</span>
          </div>
        </div>
      ) : null}
    </Card>
  );
}
