/**
 * محرر المستندات القانونية — Markdown فقط، عمداً. لا محرر قطع بصري هنا (ذاك موجود بمكان آخر
 * لمستندات المنتج العادية عبر DocBlockRenderer) — الشروط والأحكام والسياسات تُكتب كنص كامل يُلصق
 * دفعة واحدة، لا تُبنى قطعة قطعة. وضع العرض محدد بالكود (`LEGAL_EDITOR_MODE` تحت)، لا خيار يظهر
 * للمستخدم يبدّل بينه وبين شكل آخر — لو احتجنا محرر قطع بصري لمستند قانوني يوماً، يُضاف كوضع ثانٍ
 * هنا لاحقاً، لا كمفتاح تبديل بالواجهة الآن.
 *
 * المحتوى يُخزَّن بنفس شكل `Block` اللي BlockRenderer.tsx يعرفه أصلاً (`{type:"text", data:{md_ar,
 * md_en}}`) — نفس الرندرر اللي المستندات القانونية تستخدمه فعلياً، بدون أي innerHTML، فمعاينة
 * الشاشة هنا مطابقة تماماً لما يشوفه العميل. compliance-service لا يتحقق من شكل `content` إطلاقاً
 * (قاموس مفتوح)، فهذا الشكل آمن نضيفه من طرفنا بدون أي تعديل على الخدمة نفسها.
 *
 * خاص بفريقنا فقط (platform.compliance) — نفس نطاق باقي شاشات هذي الصفحة، ليس لأصحاب المحلات.
 */
import { useState } from 'react';
import { Button } from '../rj-ui/Button';
import { Field, Input, Textarea } from '../rj-ui/Field';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { BlockView, type Block } from '@base-ui/components/BlockRenderer';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { NoActionAvailable } from './NoActionAvailable';

const LEGAL_EDITOR_MODE: 'markdown' = 'markdown';

function findAction(catalog: AdminCatalog, id: string): AdminAction | undefined {
  return catalog.services.flatMap((s) => s.actions).find((a) => a.id === id);
}

export function AdminLegal({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [docId, setDocId] = useState('');
  const [version, setVersion] = useState('');
  const [titleAr, setTitleAr] = useState('');
  const [titleEn, setTitleEn] = useState('');
  const [mdAr, setMdAr] = useState('');
  const [mdEn, setMdEn] = useState('');
  const [requiresAcceptance, setRequiresAcceptance] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [drafted, setDrafted] = useState(false);
  const [armPublish, setArmPublish] = useState(false);
  const [published, setPublished] = useState(false);

  useState(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  });

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const draftAction = findAction(catalog, 'compliance.legal_draft');
  const publishAction = findAction(catalog, 'compliance.legal_publish');
  if (!draftAction || !publishAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;
  }

  const block: Block = { type: 'text', data: { md_ar: mdAr, md_en: mdEn } };
  const canDraft = docId.trim() && version.trim() && (mdAr.trim() || mdEn.trim());

  async function doDraft() {
    if (!draftAction) return;
    setBusy(true);
    setError('');
    setDrafted(false);
    setPublished(false);
    try {
      const content = {
        title: { ar: titleAr, en: titleEn },
        blocks: [block],
      };
      await req(
        draftAction.path.replace('{doc_id}', encodeURIComponent(docId)).replace('{version}', encodeURIComponent(version)),
        'PUT', { content, requires_acceptance: requiresAcceptance }, session.access_token);
      setDrafted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر حفظ المسوّدة.');
    } finally {
      setBusy(false);
    }
  }

  async function doPublish() {
    if (!publishAction) return;
    setBusy(true);
    setError('');
    try {
      await req(
        publishAction.path.replace('{doc_id}', encodeURIComponent(docId)).replace('{version}', encodeURIComponent(version)),
        'POST', undefined, session.access_token);
      setPublished(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'تعذّر النشر.');
    } finally {
      setBusy(false);
      setArmPublish(false);
    }
  }

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">المستندات القانونية</h1>
      <p className="text-sm text-text-secondary">
        اكتب أو الصق نص كامل بصيغة Markdown (عناوين بـ #، فقرات، قوائم، جداول). النشر يفتح نسخة
        رسمية جديدة — كل عميل عليه يوافق عليها من جديد تلقائياً، ولا يمكن تعديل نسخة نُشرت بالفعل.
      </p>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="معرّف المستند (doc_id)" required htmlFor="legal-doc-id">
          <Input id="legal-doc-id" dir="ltr" value={docId} onChange={(e) => setDocId(e.target.value)}
                 placeholder="privacy-policy" />
        </Field>
        <Field label="رقم النسخة" required htmlFor="legal-version">
          <Input id="legal-version" dir="ltr" value={version} onChange={(e) => setVersion(e.target.value)}
                 placeholder="1.1" />
        </Field>
        <Field label="العنوان (عربي)" htmlFor="legal-title-ar">
          <Input id="legal-title-ar" value={titleAr} onChange={(e) => setTitleAr(e.target.value)} />
        </Field>
        <Field label="العنوان (إنجليزي)" htmlFor="legal-title-en">
          <Input id="legal-title-en" dir="ltr" value={titleEn} onChange={(e) => setTitleEn(e.target.value)} />
        </Field>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={requiresAcceptance}
               onChange={(e) => setRequiresAcceptance(e.target.checked)} />
        يتطلب موافقة صريحة من العميل (وإلا فهو صفحة معلوماتية بلا بوابة)
      </label>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Field label="النص (عربي، Markdown)" htmlFor="legal-md-ar">
          <Textarea id="legal-md-ar" rows={16} value={mdAr} onChange={(e) => setMdAr(e.target.value)} />
        </Field>
        <Field label="النص (إنجليزي، Markdown)" htmlFor="legal-md-en">
          <Textarea id="legal-md-en" dir="ltr" rows={16} value={mdEn} onChange={(e) => setMdEn(e.target.value)} />
        </Field>
      </div>

      <section className="flex flex-col gap-2">
        <h2 className="text-lg font-medium">معاينة (عربي)</h2>
        <div className="rounded-card border border-border-subtle bg-surface-1 p-4">
          <BlockView block={block} locale="ar" />
        </div>
      </section>

      {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
      {drafted ? <p className="text-label text-success">حُفظت المسوّدة. راجع المعاينة، ثم انشر.</p> : null}
      {published ? <p className="text-label text-success">نُشرت. سيُطلب من العملاء الموافقة على النسخة الجديدة.</p> : null}

      <div className="flex gap-2">
        <Button onClick={doDraft} disabled={!canDraft || busy}>حفظ كمسوّدة</Button>
        <Button onClick={() => setArmPublish(true)} disabled={!drafted || busy} variant="danger">نشر</Button>
      </div>

      <ConfirmDialog open={armPublish} onClose={() => setArmPublish(false)} onConfirm={doPublish} busy={busy}
                    danger title={`نشر "${docId}" نسخة ${version}؟`}
                    body="سيصير هذا النص هو الرسمي فوراً، وكل عميل عليه موافقة سيُطلب منه الموافقة على النسخة الجديدة. لا يمكن التراجع بعد النشر." />
    </div>
  );
}
