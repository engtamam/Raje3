/**
 * Controls that configure the WHATSAPP ASSISTANT's own behaviour — never «حسابي».
 *
 * MOVED OUT OF THE ACCOUNT DOMAIN ENTIRELY, not just re-tabbed. The old AccountPanes.tsx held
 * these alongside establishment identity for historical reasons its own comments already disowned
 * ("They do NOT live in «حسابي» at all any more"); this rebuild finishes that move by giving them
 * their own file, named for the domain that actually owns them
 * (`WhatsAppAssistant.tsx`, reached from متجر التطبيقات), rather than leaving live production code
 * inside a file whose own docstring said it no longer belonged there.
 */
import { useEffect, useState } from 'react';
import { Toggle } from '../rj-ui/Toggle';
import { Card } from '../rj-ui/Card';
import { Button } from '../rj-ui/Button';
import { Field, Textarea } from '../rj-ui/Field';
import { ConfirmDialog } from '../rj-ui/ConfirmDialog';
import { Skeleton } from '../rj-ui/Skeleton';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n, tf } from '../operator-i18n';
import './account-panes-i18n';

// The categories `redact()` (services/operations/app/core/redaction.py) may report — Arabic
// labels for the transient "تم الحفظ" confirmation, so an owner learns WHAT was stripped without
// either of us ever handling the actual value a second time to tell him.
const REDACTED_KEYS: Record<string, string> = {
  iban: 'accountPanes.redacted.iban', card: 'accountPanes.redacted.card', email: 'accountPanes.redacted.email',
  national_id: 'accountPanes.redacted.national_id', phone: 'accountPanes.redacted.phone', secret: 'accountPanes.redacted.secret',
};

const AI_NOTES_MAX = 2000;

/**
 * ما يعرفه المساعد الذكي عبر واتساب عن هذا المحل تحديداً — مواعيد، سياسات، تفاصيل خدمات لا
 * يعرفها من مكان آخر على المنصة.
 *
 * A EXPLICIT SAVE BUTTON, NOT AUTOSAVE-ON-BLUR. This field is paragraphs, not a word or two — a
 * save the owner did not clearly ask for, firing because he tabbed away mid-thought, is a worse
 * failure here than the extra tap a real button costs.
 */
export function AiNotesCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const read = action(catalog, 'operations.ai_notes');
  const write = action(catalog, 'operations.set_ai_notes');
  const [text, setText] = useState<string | null | undefined>(undefined);
  const [draft, setDraft] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState('');

  useEffect(() => {
    if (!read) { setText(null); return; }
    call<{ text?: string }>(session, read)
      .then((x) => { const loadedText = x.text || ''; setText(loadedText); setDraft(loadedText); })
      .catch(() => setText(null));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!read || text === null) return null;
  if (text === undefined) return <Skeleton height={160} />;

  const overCap = draft.length > AI_NOTES_MAX;
  const dirty = draft !== text;

  async function save() {
    if (!write || overCap || busy) return;
    setBusy(true);
    setError('');
    setSaved('');
    try {
      const out = await call<{ text?: string; redacted?: string[] }>(
        session, write, { text: draft });
      const savedText = out.text || '';
      setText(savedText);
      setDraft(savedText);
      const hits = (out.redacted || []).map((c) => (REDACTED_KEYS[c] ? t(REDACTED_KEYS[c]) : c));
      setSaved(hits.length
        ? tf(t, 'accountPanes.saved.redacted', { items: hits.join(t('accountPanes.listSeparator')) })
        : t('accountPanes.saved.plain'));
    } catch (err) {
      setError(err instanceof Error ? err.message : t('accountPanes.aiNotes.saveFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <span className="flex flex-col">
        <span className="text-sm font-medium">{t('accountPanes.aiNotes.title')}</span>
        <span className="text-xs text-text-secondary">
          {t('accountPanes.aiNotes.desc')}
        </span>
      </span>

      {write ? (
        <Field
          error={overCap ? tf(t, 'accountPanes.aiNotes.tooLong', { max: AI_NOTES_MAX }) : undefined}
          hint={!overCap ? `${draft.length} / ${AI_NOTES_MAX}` : undefined}
        >
          <Textarea
            dir="rtl" rows={6} value={draft} disabled={busy}
            aria-label={t('accountPanes.aiNotes.title')}
            onChange={(e) => { setDraft(e.target.value); setSaved(''); }}
          />
        </Field>
      ) : (
        <p className="text-sm text-text-secondary">{t('accountPanes.noEditPermission')}</p>
      )}

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {saved && !dirty ? <p className="text-sm text-text-secondary">{saved}</p> : null}

      {write ? (
        <Button type="button" size="sm" className="self-start"
               disabled={!dirty || overCap || busy} onClick={save}>
          {busy ? t('accountPanes.saving') : t('accountPanes.save')}
        </Button>
      ) : null}
    </Card>
  );
}

const MSG_WORD_LIMIT_MIN = 20;
const MSG_WORD_LIMIT_MAX = 300;
const MSG_WORD_LIMIT_DEFAULT = 100;

/**
 * أطول رسالة يقبلها المساعد من العميل، بالكلمات، قبل أن يرفضها فوراً بأسلوب مؤدب ويطلب منه
 * اختصارها — بلا أي استدعاء للذكاء الاصطناعي.
 *
 * NOT RENDERED ANYWHERE TODAY (kept, not deleted — see `WhatsAppAssistant.tsx`'s own note): it
 * only gates the legacy chat engine, which does not run against real customer traffic by default
 * (WHATSAPP_DEFAULT_HANDOVER_MODE=meta) and has no equivalent in Meta Business Agent's own API.
 */
export function MsgWordLimitCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const read = action(catalog, 'operations.msg_word_limit');
  const write = action(catalog, 'operations.set_msg_word_limit');
  const [limit, setLimit] = useState<number | null | undefined>(undefined);
  const [draft, setDraft] = useState(MSG_WORD_LIMIT_DEFAULT);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!read) { setLimit(null); return; }
    call<{ limit?: number }>(session, read)
      .then((x) => { const n = x.limit ?? MSG_WORD_LIMIT_DEFAULT; setLimit(n); setDraft(n); })
      .catch(() => setLimit(null));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!read || limit === null) return null;
  if (limit === undefined) return <Skeleton height={90} />;

  const inRange = draft >= MSG_WORD_LIMIT_MIN && draft <= MSG_WORD_LIMIT_MAX;
  const dirty = draft !== limit;

  async function save() {
    if (!write || !inRange || busy) return;
    setBusy(true);
    setError('');
    setSaved(false);
    try {
      const out = await call<{ limit?: number }>(session, write, { limit: draft });
      const n = out.limit ?? draft;
      setLimit(n);
      setDraft(n);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : t('accountPanes.wordLimit.saveFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <span className="flex flex-col">
        <span className="text-sm font-medium">{t('accountPanes.wordLimit.title')}</span>
        <span className="text-xs text-text-secondary">
          {t('accountPanes.wordLimit.desc')}
        </span>
      </span>

      {write ? (
        <Field
          error={!inRange
            ? tf(t, 'accountPanes.wordLimit.range', { min: MSG_WORD_LIMIT_MIN, max: MSG_WORD_LIMIT_MAX })
            : undefined}
        >
          <input
            type="number" dir="ltr" inputMode="numeric"
            min={MSG_WORD_LIMIT_MIN} max={MSG_WORD_LIMIT_MAX} value={draft} disabled={busy}
            aria-label={t('accountPanes.wordLimit.title')}
            onChange={(e) => { setDraft(Number(e.target.value) || 0); setSaved(false); }}
            className="h-11 w-32 rounded-xl bg-surface-2 px-3"
          />
        </Field>
      ) : (
        <p className="text-sm text-text-secondary">{t('accountPanes.noLimitEditPermission')}</p>
      )}

      {error ? <p className="text-sm text-danger">{error}</p> : null}
      {saved && !dirty ? <p className="text-sm text-text-secondary">{t('accountPanes.saved.plain')}</p> : null}

      {write ? (
        <Button type="button" size="sm" className="self-start"
               disabled={!dirty || !inRange || busy} onClick={save}>
          {busy ? t('accountPanes.saving') : t('accountPanes.save')}
        </Button>
      ) : null}
    </Card>
  );
}

/**
 * المفتاح الرئيسي — تشغيل/إيقاف المساعد الذكي بالكامل، منفصل تمامًا عن الاشتراك في تطبيق واتساب
 * نفسه (services/operations/app/core/ai_toggle.py's own docstring: buying it and wanting it quiet
 * right now are two different decisions). الإيقاف يقفل المساعد تمامًا، وليس حالة "إيقاف مؤقت"
 * أخف — ولذلك يمرّ بنفس خطوة التأكيد الصريحة اللي تمرّ فيها بقية مفاتيح الثقة جنبه.
 *
 * ظاهرة فقط داخل بوابة تطبيق واتساب (AppGate بـ WhatsAppAssistant.tsx) — بلا فحص ملكية ثانٍ من
 * داخلها: هذا الإعداد يخص التطبيق نفسه، لا ميزة فرعية تحته.
 */
export function AiToggleCard({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const read = action(catalog, 'operations.ai_toggle');
  const write = action(catalog, 'operations.set_ai_toggle');
  const [enabled, setEnabled] = useState<boolean | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState<boolean | null>(null);

  useEffect(() => {
    if (!read) { setEnabled(null); return; }
    call<{ enabled?: boolean }>(session, read)
      .then((x) => setEnabled(x.enabled !== false))
      .catch(() => setEnabled(null));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!read || enabled === null) return null;
  if (enabled === undefined) return <Skeleton height={100} />;

  async function flip(next: boolean) {
    if (!write) return;
    setBusy(true);
    setError('');
    try {
      const row = await call<{ enabled?: boolean }>(session, write, { enabled: next });
      setEnabled(row.enabled !== false);
    } catch (err) {
      // THE OLD VALUE STAYS ON THE SCREEN — a toggle that moves on a failed write claims a state
      // that was never actually written.
      setError(err instanceof Error ? err.message : t('accountPanes.aiToggle.saveFailed'));
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-sm font-medium">{t('accountPanes.aiToggle.title')}</span>
          <span className="text-xs text-text-secondary">{t('accountPanes.aiToggle.desc')}</span>
        </span>
        <Toggle checked={enabled === true} disabled={busy || !write}
               onChange={(next) => setConfirming(next)}
               ariaLabel={t('accountPanes.aiToggle.title')} testId="ai-toggle" />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <ConfirmDialog open={confirming !== null} onClose={() => setConfirming(null)}
                    onConfirm={() => confirming !== null && void flip(confirming)}
                    busy={busy} danger={confirming === false}
                    title={confirming
                      ? t('accountPanes.aiToggle.confirmEnableTitle')
                      : t('accountPanes.aiToggle.confirmDisableTitle')}
                    body={confirming
                      ? t('accountPanes.aiToggle.confirmEnableBody')
                      : t('accountPanes.aiToggle.confirmDisableBody')} />
    </Card>
  );
}

/**
 * تسجيل جهات الاتصال تلقائياً عبر واتساب — أول رسالة من رقم غير معروف تسجّله كصف جهة اتصال حقيقي
 * (بلا زيارة مرفقة)، فعل حتمي بالسيرفر نفسه لا أداة يقررها الذكاء الاصطناعي — راجع
 * `services/whatsapp-assistant/app/core/conversation.py`'s الخاص بـ`_context_block` وتعليقه.
 * موقوف افتراضياً لكل محل، وتفعيله قرار ثقة المالك وحده (`operations.manage`) لأنه يعني جمع بيانات
 * حقيقية عن كل من يراسل الرقم ولو رسالة واحدة — راجع
 * `services/operations/app/core/whatsapp_auto_register.py`'s الخاص لسبب هذا الافتراض.
 *
 * ONLY BEHIND «المساعد الذكي عبر واتساب» — NOT «جهات الاتصال». The mechanism itself only ever
 * fires from inside a live WhatsApp conversation, so its real dependency was always the paid
 * assistant, never the free app. This card renders inside `<AppGate appId="whatsapp">` already
 * (WhatsAppAssistant.tsx); that outer gate is the ONLY gate, so no shop reaches this toggle
 * without holding the paid app.
 */
export function WhatsAppAutoRegisterCard({ session, catalog }: {
  session: Session; catalog: Catalog;
}) {
  const { t } = useOperatorI18n();
  const read = action(catalog, 'operations.whatsapp_auto_register');
  const write = action(catalog, 'operations.set_whatsapp_auto_register');
  const [enabled, setEnabled] = useState<boolean | null | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [confirming, setConfirming] = useState<boolean | null>(null);

  useEffect(() => {
    if (!read) { setEnabled(null); return; }
    call<{ enabled?: boolean }>(session, read)
      .then((x) => setEnabled(x.enabled === true))
      .catch(() => setEnabled(null));
  }, [session, catalog]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!read || enabled === null) return null;
  if (enabled === undefined) return <Skeleton height={100} />;

  async function flip(next: boolean) {
    if (!write) return;
    setBusy(true);
    setError('');
    try {
      const row = await call<{ enabled?: boolean }>(session, write, { enabled: next });
      setEnabled(row.enabled === true);
    } catch (err) {
      // THE OLD VALUE STAYS ON THE SCREEN — same reasoning as AiToggleCard's own comment: a
      // toggle that moves on a failed write claims a data-collection surface that was never
      // actually widened (or narrowed).
      setError(err instanceof Error ? err.message : t('accountPanes.waAutoRegister.saveFailed'));
    } finally {
      setBusy(false);
      setConfirming(null);
    }
  }

  return (
    <Card className="flex flex-col gap-2 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-sm font-medium">{t('accountPanes.waAutoRegister.title')}</span>
          <span className="text-xs text-text-secondary">
            {t('accountPanes.waAutoRegister.desc')}
          </span>
        </span>
        <Toggle checked={enabled === true} disabled={busy || !write}
               onChange={(next) => setConfirming(next)}
               ariaLabel={t('accountPanes.waAutoRegister.title')} testId="whatsapp-auto-register-toggle" />
      </div>
      {error ? <p className="text-sm text-danger">{error}</p> : null}

      <ConfirmDialog open={confirming !== null} onClose={() => setConfirming(null)}
                    onConfirm={() => confirming !== null && void flip(confirming)}
                    busy={busy} danger={confirming === true}
                    title={confirming
                      ? t('accountPanes.waAutoRegister.confirmEnableTitle')
                      : t('accountPanes.waAutoRegister.confirmDisableTitle')}
                    body={confirming
                      ? t('accountPanes.waAutoRegister.confirmEnableBody')
                      : t('accountPanes.waAutoRegister.confirmDisableBody')} />
    </Card>
  );
}
