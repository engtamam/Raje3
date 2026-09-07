/**
 * تقارير الدفاع النزاعي — بحث برقم جوال، بطاقات سيناريو (لا قائمة منسدلة، بطلب صريح: الرمز
 * الإنجليزي "data_loss" لا يعني شيئاً لأدمن يقرأ شاشة تحت ضغط نزاع حقيقي)، ثم ملف جاهز للتنزيل.
 *
 * الوصول من "المنصّة والفريق" — قرار متعمّد: لا عنصر سابع بالشريط الجانبي (انظر تعليق AdminNav.tsx
 * الخاص بحد 5-6 عناصر)، بس التصميم نفسه صفحة كاملة مستقلة بصرياً، لا نموذج مضغوط داخل تبويب.
 *
 * التنزيل حقيقي، لا رابط JSON: الخادم يرجّع الملف نفسه (docx أو pdf)، فهذي الشاشة تطلب Blob
 * وتُنزّله يدوياً — المسار الوحيد بالكونسول اللي يحتاج هذا (كل شاشة ثانية تتعامل مع JSON بس).
 */
import { useState } from 'react';
import {
  Search, HardDriveDownload, Receipt, BellOff, FileWarning, ShieldAlert, Bot, MailWarning,
  FileText, Download, Loader2, TriangleAlert,
} from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Input, Field } from '../rj-ui/Field';
import { Segmented } from '../rj-ui/Segmented';
import { Badge } from '../rj-ui/Badge';
import { fetchCatalog, type AdminCatalog } from './catalog';
import { AdminRefused, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';
import { sentenceFor } from '../api';
import { digitsOnly } from '../digits';

type ScenarioId =
  | 'data_loss' | 'billing_error' | 'suspended_no_notice' | 'contract_breach'
  | 'suspended_tos' | 'ai_hallucination' | 'unauthorized_marketing';

const SCENARIOS: { id: ScenarioId; label: string; hint: string; icon: typeof Search }[] = [
  { id: 'data_loss', label: 'فقدان بيانات', hint: 'المحل يقول فقدنا بياناته أو ما فيه نسخة احتياطية',
    icon: HardDriveDownload },
  { id: 'billing_error', label: 'خطأ فوترة', hint: 'اعتراض على اشتراك أو فاتورة أو مبلغ مسحوب',
    icon: Receipt },
  { id: 'suspended_no_notice', label: 'تعليق بدون إشعار', hint: 'المحل يقول عُلّق حسابه بلا سبب أو تنبيه',
    icon: BellOff },
  { id: 'contract_breach', label: 'خرق عقد', hint: 'اعتراض على بند بالشروط أو اتفاقية الخدمة',
    icon: FileWarning },
  { id: 'suspended_tos', label: 'تعليق لمخالفة الشروط', hint: 'المحل يعترض على تعليقه لمخالفة مزعومة',
    icon: ShieldAlert },
  { id: 'ai_hallucination', label: 'هلوسة الذكاء الاصطناعي', hint: 'المحل يقول البوت نفّذ شي بدون تأكيده',
    icon: Bot },
  { id: 'unauthorized_marketing', label: 'تسويق غير مصرَّح', hint: 'اعتراض على رسالة تسويقية وصلت بلا إذن',
    icon: MailWarning },
];

type Phase = 'idle' | 'generating' | 'done' | 'failed';

export function AdminDisputeReports({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [phone, setPhone] = useState('');
  const [scenario, setScenario] = useState<ScenarioId | ''>('');
  const [format, setFormat] = useState<'docx' | 'pdf'>('docx');
  const [phase, setPhase] = useState<Phase>('idle');
  const [error, setError] = useState('');
  const [file, setFile] = useState<{ blob: Blob; name: string } | null>(null);

  useState(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  });

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const action = catalog.services.flatMap((s) => s.actions).find((a) => a.id === 'insights.dispute_report');
  if (!action) return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;

  const ready = /^05\d{8}$/.test(phone) && scenario !== '';

  async function generate() {
    if (!ready) return;
    setPhase('generating');
    setError('');
    setFile(null);
    try {
      const res = await fetch(action!.path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${session.access_token}` },
        body: JSON.stringify({ phone, scenario, file_format: format }),
      });
      if (!res.ok) {
        let reason = 'تعذّر توليد التقرير.';
        try { reason = (await res.json()).reason || (await res.json()).message || reason; } catch { /* not json */ }
        throw new AdminRefused(reason);
      }
      const disposition = res.headers.get('content-disposition') || '';
      const nameMatch = /filename="?([^";]+)"?/.exec(disposition);
      const blob = await res.blob();
      setFile({ blob, name: nameMatch?.[1] || `dispute_${scenario}.${format}` });
      setPhase('done');
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر توليد التقرير.'));
      setPhase('failed');
    }
  }

  function download() {
    if (!file) return;
    const url = URL.createObjectURL(file.blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = file.name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="flex flex-col gap-8 p-6">
      <div className="flex flex-col gap-1 text-center">
        <h1 className="text-2xl font-bold leading-tight tracking-tight">تقارير الدفاع النزاعي</h1>
        <p className="text-sm text-text-secondary">
          ملف أدلة جاهز يدافع عن راجِع عند اعتراض محل — رقم جواله، نوع الاعتراض، وخلاص.
        </p>
      </div>

      {/* شريط البحث — كبير، بمنتصف الصفحة، أول شي يُلمس */}
      <div className="mx-auto w-full max-w-md">
        <Field label="رقم جوال مالك المنشأة" htmlFor="dispute-phone">
          <div className="relative">
            <Search size={18} className="pointer-events-none absolute start-3 top-1/2 -translate-y-1/2 text-text-secondary" />
            <Input id="dispute-phone" dir="ltr" inputMode="tel" placeholder="05xxxxxxxx"
                  value={phone} onChange={(e) => setPhone(digitsOnly(e.target.value).slice(0, 10))}
                  className="h-14 ps-10 text-center text-xl font-semibold tracking-wide" />
          </div>
        </Field>
      </div>

      {/* بطاقات السيناريو — لا قائمة منسدلة */}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {SCENARIOS.map((s) => {
          const Icon = s.icon;
          const on = scenario === s.id;
          return (
            <button
              key={s.id}
              type="button"
              onClick={() => setScenario(s.id)}
              aria-pressed={on}
              className={`flex flex-col items-start gap-2 rounded-2xl border p-4 text-start shadow-sm transition-all ${
                on
                  ? 'border-accent bg-accent-soft ring-2 ring-accent'
                  : 'border-border-subtle bg-surface-1 hover:border-border-strong'
              }`}
            >
              <div className="rounded-xl bg-surface-2 p-2 text-text-secondary">
                <Icon size={22} />
              </div>
              <span className="font-semibold">{s.label}</span>
              <span className="text-xs text-text-secondary">{s.hint}</span>
            </button>
          );
        })}
      </div>

      {/* الصيغة + زر التوليد */}
      <div className="mx-auto flex w-full max-w-md flex-col items-center gap-4">
        <Segmented value={format} onChange={(v) => setFormat(v as 'docx' | 'pdf')}
                  options={[{ value: 'docx', label: 'Word' }, { value: 'pdf', label: 'PDF' }]} />
        <Button size="lg" disabled={!ready || phase === 'generating'} onClick={generate} className="w-full">
          {phase === 'generating' ? (
            <span className="flex items-center gap-2"><Loader2 size={18} className="animate-spin" /> يجمع الأدلة من كل المصادر…</span>
          ) : 'توليد التقرير'}
        </Button>
      </div>

      {/* النتيجة */}
      {phase === 'done' && file ? (
        <div className="mx-auto flex w-full max-w-md flex-col items-center gap-3 rounded-2xl border border-success/30 bg-success/5 p-6 text-center">
          <FileText size={40} className="text-success" />
          <p className="font-semibold">الملف جاهز</p>
          <p dir="ltr" className="text-xs text-text-secondary">{file.name}</p>
          <Button onClick={download} className="gap-2"><Download size={16} /> تنزيل الملف</Button>
        </div>
      ) : null}

      {phase === 'failed' && error ? (
        <div className="mx-auto flex w-full max-w-md items-center gap-2 rounded-xl border border-danger/30 bg-danger/5 p-4 text-sm text-danger">
          <TriangleAlert size={18} className="shrink-0" />
          {error}
        </div>
      ) : null}
    </div>
  );
}
