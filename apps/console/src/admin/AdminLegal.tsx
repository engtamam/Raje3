/**
 * محرر المستندات القانونية — Markdown فقط، عمداً. لا محرر قطع بصري هنا (ذاك موجود بمكان آخر
 * لمستندات المنتج العادية عبر DocBlockRenderer) — الشروط والأحكام والسياسات تُكتب كنص كامل يُلصق
 * دفعة واحدة، لا تُبنى قطعة قطعة. وضع العرض محدد بالكود (`LEGAL_EDITOR_MODE` تحت)، لا خيار يظهر
 * للمستخدم يبدّل بينه وبين شكل آخر — لو احتجنا محرر قطع بصري لمستند قانوني يوماً، يُضاف كوضع ثانٍ
 * هنا لاحقاً، لا كمفتاح تبديل بالواجهة الآن.
 *
 * تصحيح صار بعد الإطلاق الأول (المعاينة هنا كانت تبدو سليمة والعميل الحقيقي ما يقدر يقرأ شي):
 * الشاشة تكتب Markdown وتعاين بـ`BlockView`/`Block` (`{type:"text", data:{md_ar,md_en}}`) — هذا
 * صحيح للمعاينة المحلية فقط. لكن العميل الحقيقي، وقت قبول المستند (`AcceptTerms.tsx`)، يقرأ
 * المحتوى عبر `DocBlocksView` (رندرر compliance المُوحَّد، شكل `{kind:{...}}` مفتاح واحد) — وهذا
 * رندرر مختلف تماماً بشكل مختلف، ليس نفس `BlockRenderer`. فما يُرسَل للخادم يُغلَّف بشكل
 * `{legal_text:{md_ar,md_en}}` (الشِّيم اللي `legalToDocBlocks.ts`/`DocBlockRenderer.tsx` يعرفانه
 * تحت اسم `legal_*`)، لا بشكل `{type,data}` الخام — وإلا DocBlocksView ما يعرف يفكّه ويطلع فاضياً
 * عند العميل رغم أن معاينة هذي الشاشة كانت تبدو سليمة. compliance-service لا يتحقق من شكل
 * `content` إطلاقاً (قاموس مفتوح)، فهذا الشكل آمن نضيفه من طرفنا بدون أي تعديل على الخدمة نفسها.
 *
 * شاشة إدارة حقيقية، لا نموذج فاضٍ: عمود يسار بكل أنواع المستندات الموجودة فعلاً (منشور أو مسوّدة
 * لم تُنشر بعد — `compliance.legal_list` يرجّع الاثنين، انظر تعليق الخادم نفسه بـ`legal_pages.py`)،
 * وعمود يمين بسجل كل نسخة لنوع مُختار (`compliance.legal_history`) + نموذج إصدار نسخة جديدة له،
 * أو زر "نوع جديد" يفتح نفس النموذج فاضياً لأي doc_id حر — الخادم لا يقيّد الأنواع بقائمة ثابتة.
 *
 * خاص بفريقنا فقط (platform.compliance) — نفس نطاق باقي شاشات هذي الصفحة، ليس لأصحاب المحلات.
 */
import { useEffect, useState } from 'react';
import { FilePlus2, FileText, FileClock, CircleDot } from 'lucide-react';
import { Button } from '../rj-ui/Button';
import { Field, Input, Textarea } from '../rj-ui/Field';
import { Badge } from '../rj-ui/Badge';
import { Segmented } from '../rj-ui/Segmented';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { BlockView, type Block } from '@base-ui/components/BlockRenderer';
import { fetchCatalog, type AdminAction, type AdminCatalog } from './catalog';
import { req, type AdminSession } from './api';
import { sentenceFor } from '../api';
import { NoActionAvailable } from './NoActionAvailable';

function findAction(catalog: AdminCatalog, id: string): AdminAction | undefined {
  return catalog.services.flatMap((s) => s.actions).find((a) => a.id === id);
}

// SAME TITLES AS seed-legal.sh's OWN `TITLES` — `GET /legal` returns only a doc_id, never a
// title, so a slug like "processing-agreement" was the ONLY thing the list could show (reported
// live: "why does it only show the English slug"). Kept here rather than fetched per-row (the
// history/view routes have a title, but that is one extra network call per card just to render a
// list). A brand-new type not in this map still shows fine — its own doc_id, just without an
// Arabic label above it, exactly the pre-existing behaviour for anything unrecognised.
const DOC_TITLES: Record<string, { ar: string; en: string }> = {
  'privacy-policy': { ar: 'سياسة الخصوصية', en: 'Privacy Policy' },
  'data-subject-rights': { ar: 'إجراء حقوق أصحاب البيانات', en: 'Data Subject Rights Procedure' },
  ropa: { ar: 'سجل أنشطة معالجة البيانات الشخصية', en: 'Records of Processing Activities (ROPA)' },
  dpia: { ar: 'تقييم الأثر لحماية البيانات الشخصية', en: 'Data Protection Impact Assessment (DPIA)' },
  cookies: { ar: 'سياسة ملفات الارتباط والتقنيات المتتبِّعة', en: 'Cookies & Tracking Technologies Policy' },
  'processing-agreement': { ar: 'اتفاقية معالجة البيانات', en: 'Data Processing Agreement' },
  'processor-dpa': { ar: 'اتفاقية معالجة البيانات (التزامات المعالِج)',
    en: "Data Processing Agreement (Processor's Commitments)" },
  terms: { ar: 'الشروط والأحكام', en: 'Terms of Service' },
  'affiliate-privacy-policy': { ar: 'سياسة خصوصية المسوّقين', en: 'Affiliate Privacy Policy' },
  'affiliate-agreement': { ar: 'اتفاقية المسوّقين والمقاولين المستقلين', en: 'Affiliate Agreement' },
};

interface DocRow {
  doc_id: string;
  version: string | null;
  status: 'published' | 'draft';
  requires_acceptance: boolean;
}

interface VersionRow {
  version: string;
  status: 'draft' | 'published';
  published_at: number;
  requires_acceptance: boolean;
}

export function AdminLegal({ session }: { session: AdminSession }) {
  const [catalog, setCatalog] = useState<AdminCatalog | 'loading' | 'failed'>('loading');
  const [docs, setDocs] = useState<DocRow[] | 'loading' | 'failed'>('loading');
  const [selected, setSelected] = useState('');       // doc_id currently open, '' = none / "new type"
  const [history, setHistory] = useState<VersionRow[] | 'loading' | 'failed'>('loading');

  const [docId, setDocId] = useState('');
  const [version, setVersion] = useState('');
  const [titleAr, setTitleAr] = useState('');
  const [titleEn, setTitleEn] = useState('');
  const [mdAr, setMdAr] = useState('');
  const [mdEn, setMdEn] = useState('');
  // WHICH LANGUAGE IS BEING WRITTEN RIGHT NOW — one at a time, on request: writing a long legal
  // text with both editions side by side splits attention and halves the usable width of each.
  // Switching does not lose the other language's text; it is still there, just off-screen.
  const [lang, setLang] = useState<'ar' | 'en'>('ar');
  const [requiresAcceptance, setRequiresAcceptance] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [drafted, setDrafted] = useState(false);
  const [armPublish, setArmPublish] = useState(false);
  const [published, setPublished] = useState(false);

  useState(() => {
    fetchCatalog(session).then(setCatalog).catch(() => setCatalog('failed'));
  });

  const listAction = catalog !== 'loading' && catalog !== 'failed' ? findAction(catalog, 'compliance.legal_list') : undefined;
  const historyAction = catalog !== 'loading' && catalog !== 'failed' ? findAction(catalog, 'compliance.legal_history') : undefined;
  const viewAction = catalog !== 'loading' && catalog !== 'failed' ? findAction(catalog, 'compliance.legal_view') : undefined;

  useEffect(() => {
    if (!listAction) return;
    setDocs('loading');
    req<{ documents: DocRow[] }>(listAction.path, 'GET', undefined, session.access_token)
      .then((r) => setDocs(r.documents))
      .catch(() => setDocs('failed'));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [catalog]);

  // LOADS ONE SPECIFIC VERSION'S TEXT INTO THE EDITOR. `version` empty means "whatever is
  // currently published" — which is NOT necessarily the newest row in the history list: a fresh
  // draft (e.g. just seeded from the Markdown files) has no `published_at` and sits UNDER the
  // still-live older version until somebody publishes it. Opening a type used to always load the
  // published one, so a brand-new draft's own text stayed invisible — the empty-editor screenshot
  // was privacy-policy v1 (old, non-legal_text content) still "current" while v2 (the real,
  // reviewable draft) sat unopened right next to it. Every history row now has its own "فتح" to
  // load exactly that version, draft or published.
  function loadVersion(id: string, version?: string) {
    if (!viewAction) return;
    const path = viewAction.path.replace('{doc_id}', encodeURIComponent(id))
      + (version ? `?version=${encodeURIComponent(version)}` : '');
    req<{ title?: string; blocks?: { legal_text?: { md_ar?: string; md_en?: string } }[] }>(
      path, 'GET', undefined, session.access_token)
      .then((r) => {
        const text = r.blocks?.find((b) => b.legal_text)?.legal_text;
        setMdAr(text?.md_ar || ''); setMdEn(text?.md_en || '');
      })
      .catch(() => { /* nothing published yet, or an old non-markdown version — leave blank */ });
  }

  function openType(id: string) {
    setSelected(id);
    setDocId(id);
    setVersion('');
    setTitleAr(''); setTitleEn(''); setMdAr(''); setMdEn('');
    setRequiresAcceptance(true);
    setDrafted(false); setPublished(false); setError('');
    if (!historyAction) return;
    setHistory('loading');
    req<{ versions: VersionRow[] }>(
      historyAction.path.replace('{doc_id}', encodeURIComponent(id)),
      'GET', undefined, session.access_token)
      .then((r) => setHistory(r.versions.sort((a, b) => b.published_at - a.published_at)))
      .catch(() => setHistory('failed'));

    loadVersion(id);   // whatever is currently published, as a starting point
  }

  function openNewType() {
    setSelected('__new__');
    setDocId(''); setVersion('');
    setTitleAr(''); setTitleEn(''); setMdAr(''); setMdEn('');
    setRequiresAcceptance(true);
    setDrafted(false); setPublished(false); setError('');
    setHistory([]);
  }

  if (catalog === 'loading') return <p className="p-6 text-sm text-text-secondary">جارٍ التحميل…</p>;
  if (catalog === 'failed') return <p role="alert" className="p-6 text-danger">تعذّرت قراءة كتالوج الإدارة.</p>;

  const draftAction = findAction(catalog, 'compliance.legal_draft');
  const publishAction = findAction(catalog, 'compliance.legal_publish');
  if (!draftAction || !publishAction || !listAction || !historyAction) {
    return <NoActionAvailable catalog={catalog} permissionTitle="هذه الشاشة ليست ضمن صلاحياتك" />;
  }

  // `block` is ONLY for this screen's own preview (BlockView reads {type,data}). What actually
  // ships to the server is `legal_text` below — DocBlocksView's shape, see the header note.
  const block: Block = { type: 'text', data: { md_ar: mdAr, md_en: mdEn } };
  const canDraft = docId.trim() && version.trim() && (mdAr.trim() || mdEn.trim());

  async function refreshTypeAfterChange() {
    req<{ documents: DocRow[] }>(listAction!.path, 'GET', undefined, session.access_token)
      .then((r) => setDocs(r.documents)).catch(() => {});
    if (!selected || selected === '__new__') return;
    req<{ versions: VersionRow[] }>(
      historyAction!.path.replace('{doc_id}', encodeURIComponent(selected)),
      'GET', undefined, session.access_token)
      .then((r) => setHistory(r.versions.sort((a, b) => b.published_at - a.published_at)))
      .catch(() => {});
  }

  async function doDraft() {
    setBusy(true);
    setError('');
    setDrafted(false);
    setPublished(false);
    try {
      const content = {
        title: { ar: titleAr, en: titleEn },
        blocks: [{ legal_text: { md_ar: mdAr, md_en: mdEn } }],
      };
      await req(
        draftAction!.path.replace('{doc_id}', encodeURIComponent(docId)).replace('{version}', encodeURIComponent(version)),
        'PUT', { content, requires_acceptance: requiresAcceptance }, session.access_token);
      setDrafted(true);
      setSelected(docId);
      await refreshTypeAfterChange();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر حفظ المسوّدة.'));
    } finally {
      setBusy(false);
    }
  }

  async function doPublish() {
    setBusy(true);
    setError('');
    try {
      await req(
        publishAction!.path.replace('{doc_id}', encodeURIComponent(docId)).replace('{version}', encodeURIComponent(version)),
        'POST', undefined, session.access_token);
      setPublished(true);
      await refreshTypeAfterChange();
    } catch (err) {
      setError(sentenceFor(err, 'تعذّر النشر.'));
    } finally {
      setBusy(false);
      setArmPublish(false);
    }
  }

  return (
    <div className="flex flex-col gap-4 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl leading-tight tracking-tight">المستندات القانونية</h1>
          <p className="text-sm text-text-secondary">
            كل نوع مستند بنسخه — النشر يفتح نسخة رسمية جديدة، ولا يمكن تعديل نسخة نُشرت بالفعل.
          </p>
        </div>
        <Button onClick={openNewType} className="gap-2"><FilePlus2 size={16} /> نوع مستند جديد</Button>
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-[280px_1fr]">
        {/* عمود الأنواع الموجودة فعلاً */}
        <div className="flex flex-col gap-2">
          {docs === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p> : null}
          {docs === 'failed' ? <p role="alert" className="text-sm text-danger">تعذّرت قراءة قائمة المستندات.</p> : null}
          {Array.isArray(docs) && docs.length === 0 ? (
            <p className="text-sm text-text-secondary">لا يوجد أي مستند بعد — ابدأ بـ"نوع مستند جديد".</p>
          ) : null}
          {Array.isArray(docs) ? docs.map((d) => (
            <button
              key={d.doc_id}
              type="button"
              onClick={() => openType(d.doc_id)}
              className={`flex flex-col items-start gap-1 rounded-xl border p-3 text-start transition-colors ${
                selected === d.doc_id
                  ? 'border-accent bg-accent-soft ring-1 ring-accent'
                  : 'border-border-subtle bg-surface-1 hover:border-border-strong'
              }`}
            >
              {DOC_TITLES[d.doc_id] ? (
                <>
                  <span className="text-sm font-medium">{DOC_TITLES[d.doc_id].ar}</span>
                  <span dir="ltr" className="font-mono text-xs text-text-secondary">{d.doc_id}</span>
                </>
              ) : (
                <span dir="ltr" className="font-mono text-sm font-medium">{d.doc_id}</span>
              )}
              <span className="flex items-center gap-1.5 text-xs text-text-secondary">
                {/* compliance-service doesn't stamp `status` on published rows yet (patch sent,
                    not shipped as of this writing) — `version` being non-null is the same fact
                    either way, so fall back to it rather than break until that ships. */}
                {d.status === 'published' || (d.status === undefined && d.version) ? (
                  <Badge tone="success" className="gap-1"><CircleDot size={10} /> منشور — نسخة {d.version}</Badge>
                ) : (
                  <Badge tone="warning" className="gap-1"><FileClock size={10} /> مسوّدة، لم يُنشر</Badge>
                )}
                {d.requires_acceptance ? <span>يتطلب موافقة</span> : null}
              </span>
            </button>
          )) : null}
        </div>

        {/* عمود التفاصيل: سجل النسخ + نموذج إصدار جديد */}
        {selected ? (
          <div className="flex flex-col gap-6">
            {selected !== '__new__' ? (
              <section className="flex flex-col gap-2">
                <h2 className="text-lg font-medium">سجل النسخ — <span dir="ltr" className="font-mono">{selected}</span></h2>
                {history === 'loading' ? <p className="text-sm text-text-secondary">جارٍ التحميل…</p> : null}
                {history === 'failed' ? <p role="alert" className="text-sm text-danger">تعذّرت قراءة السجل.</p> : null}
                {Array.isArray(history) ? (
                  <div className="flex flex-col gap-1.5">
                    {history.map((v) => (
                      <div key={v.version} className="flex items-center gap-2 rounded-lg border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
                        <FileText size={14} className="text-text-secondary" />
                        <span dir="ltr" className="font-mono">{v.version}</span>
                        <Badge tone={v.status === 'published' ? 'success' : 'neutral'}>
                          {v.status === 'published' ? 'منشور' : 'مسوّدة'}
                        </Badge>
                        {v.published_at ? (
                          <span className="text-xs text-text-secondary">
                            {new Date(v.published_at * 1000).toLocaleDateString('ar-SA-u-nu-latn')}
                          </span>
                        ) : null}
                        <button type="button" className="ms-auto text-xs text-text-secondary hover:underline"
                                onClick={() => loadVersion(selected, v.version)}>
                          فتح
                        </button>
                        <button type="button" className="text-xs text-text-secondary hover:underline"
                                onClick={() => setVersion(`${(Number(v.version) || 0) + 0.1 || '2.0'}`)}>
                          إصدار نسخة تالية
                        </button>
                      </div>
                    ))}
                  </div>
                ) : null}
              </section>
            ) : (
              <p className="text-sm text-text-secondary">اكتب معرّف (slug) لنوع مستند لم يوجد من قبل — أي نص حر، مثل <span dir="ltr" className="font-mono">refund-policy</span>.</p>
            )}

            <section className="flex flex-col gap-4 rounded-2xl border border-border-subtle bg-surface-1 p-4">
              <h2 className="text-lg font-medium">
                {selected === '__new__' ? 'نوع مستند جديد' : 'إصدار نسخة جديدة'}
              </h2>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <Field label="معرّف المستند (doc_id)" required htmlFor="legal-doc-id">
                  <Input id="legal-doc-id" dir="ltr" value={docId}
                        disabled={selected !== '__new__'}
                        onChange={(e) => setDocId(e.target.value)} placeholder="privacy-policy" />
                </Field>
                <Field label="رقم النسخة" required htmlFor="legal-version">
                  <Input id="legal-version" dir="ltr" value={version} onChange={(e) => setVersion(e.target.value)}
                        placeholder="1.1" />
                </Field>
              </div>

              <label className="flex items-center gap-2 text-sm">
                <input type="checkbox" checked={requiresAcceptance}
                      onChange={(e) => setRequiresAcceptance(e.target.checked)} />
                يتطلب موافقة صريحة من العميل (وإلا فهو صفحة معلوماتية بلا بوابة)
              </label>

              {/* لغة واحدة تُكتب وتُعاين بكل مرة — تبديل، لا عرض الاثنتين جنباً لجنب */}
              <Segmented value={lang} onChange={(v) => setLang(v as 'ar' | 'en')}
                        options={[{ value: 'ar', label: 'عربي' }, { value: 'en', label: 'English' }]} />

              {lang === 'ar' ? (
                <div className="flex flex-col gap-4">
                  <Field label="العنوان (عربي)" htmlFor="legal-title-ar">
                    <Input id="legal-title-ar" value={titleAr} onChange={(e) => setTitleAr(e.target.value)} />
                  </Field>
                  <Field label="النص (عربي، Markdown)" htmlFor="legal-md-ar">
                    <Textarea id="legal-md-ar" rows={18} value={mdAr} onChange={(e) => setMdAr(e.target.value)} />
                  </Field>
                </div>
              ) : (
                <div className="flex flex-col gap-4" dir="ltr">
                  <Field label="Title (English)" htmlFor="legal-title-en">
                    <Input id="legal-title-en" value={titleEn} onChange={(e) => setTitleEn(e.target.value)} />
                  </Field>
                  <Field label="Text (English, Markdown)" htmlFor="legal-md-en">
                    <Textarea id="legal-md-en" rows={18} value={mdEn} onChange={(e) => setMdEn(e.target.value)} />
                  </Field>
                </div>
              )}

              <section className="flex flex-col gap-2">
                <h3 className="text-sm font-medium text-text-secondary">
                  {lang === 'ar' ? 'معاينة (عربي)' : 'Preview (English)'}
                </h3>
                <div className="rounded-card border border-border-subtle bg-surface-0 p-4">
                  <BlockView block={block} locale={lang} />
                </div>
              </section>

              {error ? <p role="alert" className="text-danger text-sm">{error}</p> : null}
              {drafted ? <p className="text-label text-success">حُفظت المسوّدة. راجع المعاينة، ثم انشر.</p> : null}
              {published ? <p className="text-label text-success">نُشرت. سيُطلب من العملاء الموافقة على النسخة الجديدة.</p> : null}

              <div className="flex gap-2">
                <Button onClick={doDraft} disabled={!canDraft || busy}>حفظ كمسوّدة</Button>
                <Button onClick={() => setArmPublish(true)} disabled={!drafted || busy} variant="danger">نشر</Button>
              </div>
            </section>
          </div>
        ) : (
          <p className="p-6 text-sm text-text-secondary">اختر نوع مستند من القائمة، أو ابدأ نوعاً جديداً.</p>
        )}
      </div>

      <ConfirmDialog open={armPublish} onClose={() => setArmPublish(false)} onConfirm={doPublish} busy={busy}
                    danger title={`نشر "${docId}" نسخة ${version}؟`}
                    body="سيصير هذا النص هو الرسمي فوراً، وكل عميل عليه موافقة سيُطلب منه الموافقة على النسخة الجديدة. لا يمكن التراجع بعد النشر." />
    </div>
  );
}
