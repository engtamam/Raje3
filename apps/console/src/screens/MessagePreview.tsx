/**
 * One message, as the customer will read it — and the wordings he may choose between.
 *
 * WHY A PREVIEW AND NOT A LIST OF NAMES. «تأكيد الزيارة» is a name; «يا هلا محمد، نوّرتنا اليوم في
 * مغسلة النخيل» is the thing he is deciding about. An owner asked to pick between "warm" and
 * "feminine" is being asked to imagine two messages; an owner shown two bubbles is reading.
 *
 * THE TEXT COMES RENDERED FROM THE ENGINE, never assembled here. It goes through the same
 * `render()` a real send goes through, so a wording that cannot render is one he is never offered
 * — and what he reads on this screen is what leaves the building. A screen that filled the blanks
 * itself would eventually show a message that works here and fails there, and this is the one
 * place that must not lie.
 *
 * AND IT IS A CHAT, NOT A FORM. The bubble, the tail, the paper behind it: he has seen this
 * shape ten thousand times, so he judges the words instead of learning a layout.
 */
import { useEffect, useState } from 'react';
// STAYS ON THE KIT'S MODAL, DELIBERATELY. This screen opens TextEditor NESTED inside itself
// (`writing`, below) — and the kit's Modal is the one with an actual stacking registry, so only
// the top dialog binds Escape when two are open together. rj-ui/Modal is single-dialog only by
// its own scope note; swapping just this one half of the pair would not make them coordinate —
// the registry only knows about other kit Modals — so both stay on it rather than one.
import { Modal } from '@base-ui/design-system/Modal';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { isDenied, isReady, DENIED, hasFailed, isLoading, type Loading } from '../loading';
import { Skeleton } from '../rj-ui/Skeleton';
import { Check, ExternalLink, Eye, Lock, Sparkles } from 'lucide-react';
import { TextEditor, type Mandatory, type Slot } from './TextEditor';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { WaFlowScreens, WhatsAppTemplatePreview, type FlowJson } from '../rj-ui/WhatsAppPreview';
import { useOperatorI18n } from '../operator-i18n';
import './message-preview-i18n';

/**
 * ONE BUTTON UNDER THE BUBBLE — Meta draws these OUTSIDE the message, not inside it, and the two
 * kinds land the customer in different places: `url` leaves WhatsApp for a website; `flow` opens
 * WhatsApp's OWN screens (our booking Flow, for instance) without ever leaving the app. An owner
 * deciding on a wording needs to see which one his customer actually gets, not just the label.
 */
export interface MessageButton {
  label: string;
  kind: 'flow' | 'url';
  /** The Flow's registered name (`booking_flow`, `rating_flow`, …) — present only for `kind:
   *  'flow'`, snake_case straight off the server like every other field on this row (see
   *  `owner.py`'s own comment on why this rides along now). Absent means "show the button, but
   *  it cannot be opened here" rather than a broken fetch. */
  flow_name?: string;
}

export interface Option {
  name: string; tone: string; text: string; mine?: boolean;
  /** The wording AS WRITTEN, with «[اسم العميل]» where a blank is — see the sheet. */
  template?: string;
  /** Can this wording actually leave today, on HIS number. `null`/absent is NOT KNOWN — the
   *  reader that answers it says so when it could not ask, and a verdict we did not get must
   *  never be drawn as one. */
  approved?: boolean | null;
  /** For his own texts: where it stands with Meta, and Meta's words when it was refused. */
  status?: string;
  reason?: string;
  /** The button(s) Meta renders under this bubble, if the template carries one. Absent for an
   *  ordinary text message — most of them. */
  buttons?: MessageButton[];
}

/** What a row says about itself, in his words — never Meta's status names. Defaults `t` to the
 *  Arabic original (see BookingDialog.tsx's own `blockedSentence` for the same pattern) so this
 *  stays a plain, hook-free function callable outside a component tree; real render call sites
 *  pass the live translator instead. */
export function standing(
  o: Option,
  t: (key: string) => string = (k) => ({
    'messagePreview.status.rejected': 'رفضها واتساب',
    'messagePreview.status.pendingReview': 'عند واتساب للمراجعة',
    'messagePreview.status.notSubmitted': 'لم تُرفَع بعد',
    'messagePreview.status.ready': 'جاهزة للإرسال',
    'messagePreview.status.awaitingApproval': 'بانتظار اعتماد واتساب',
  }[k] ?? k),
): { label: string; tone: 'success' | 'warning' | 'danger' | 'neutral' } | null {
  if (o.mine && o.status === 'rejected') return { label: t('messagePreview.status.rejected'), tone: 'danger' };
  if (o.mine && o.status === 'pending') return { label: t('messagePreview.status.pendingReview'), tone: 'warning' };
  if (o.mine && o.status === 'draft') return { label: t('messagePreview.status.notSubmitted'), tone: 'neutral' };
  // NOT KNOWN DRAWS NOTHING. "not ready" about a wording we simply could not ask about is the
  // same defect as "under WhatsApp review" about one that was never submitted, one row smaller.
  if (o.approved === true) return { label: t('messagePreview.status.ready'), tone: 'success' };
  if (o.approved === false) return { label: t('messagePreview.status.awaitingApproval'), tone: 'warning' };
  return null;
}

/** One of his own texts that is not sending yet — and why it is not. */
interface Mine { name: string; status: string; reason?: string; body: string }
interface HelpRow { name: string; status: string; answer?: string }

/** The states are Meta's, and they are said in his words rather than theirs. */
const STATUS: Record<string, string> = {
  draft: 'مسودّة — لم تُرفَع بعد',
  pending: 'عند واتساب للمراجعة',
  rejected: 'رفضها واتساب',
  retired: 'استبدلتها بنسخة أحدث',
};

/** The two voices, named for an owner rather than for a library.
 *
 * A REAL PAIR, NOT A MISMATCHED ONE — this used to read {warm: 'ودّية', feminine: 'مؤنثة'}: a
 * STYLE word ("friendly") set against a GRAMMATICAL-GENDER word ("feminine"), which is not the
 * axis it looks like on screen (owner's own screenshot: two cards captioned «ودية» and «مؤنثة»,
 * which reads as two different scales, not one choice). The two templates only ever differ in
 * which gender they address the customer as (reasons.py's own note: the feminine tone conjugates
 * every verb — «نوّرتِنا», «أخذتِ»), so the labels now say exactly that: مذكر/مؤنث.
 *
 * THE CODE VALUES STAY `warm`/`feminine` — reminders' own `tone` field, already the shape stored
 * per subscriber and read throughout core/reasons.py; renaming the wire value is a data migration,
 * not a label fix, and every subscriber's real choice keeps working unchanged either way. Only
 * what an owner reads on this screen changes. */
function toneLabel(t: (key: string) => string, tone: string): string {
  return tone === 'warm' ? t('messagePreview.tone.warm') : tone === 'feminine' ? t('messagePreview.tone.feminine') : tone;
}

export function MessagePreview({
  session, catalog, reasonId, templateType, label, when, canRetext, onClose, onChosen,
}: {
  session: Session;
  catalog: Catalog;
  /** Either this OR `templateType` — never neither. */
  reasonId?: string;
  /**
   * A CAMPAIGN GOAL WITH NO REASON OF ITS OWN — announce, awareness,
   * service_offer, package_offer (see Launch.tsx's own GOAL_REASON_ID). Reads
   * `reminders.preview_by_type` instead of `reminders.preview_reason`, and drops everything
   * that only makes sense attached to a reason row: his own texts, the switch, retexting.
   */
  templateType?: string;
  label: string;
  when: string;
  canRetext: boolean;
  onClose: () => void;
  onChosen: () => void;
}) {
  const { t } = useOperatorI18n();
  // A REASON HAS ONE, A BARE TEMPLATE TYPE DOES NOT — his own texts, submitting, «ساعدوني»,
  // switching the shop's chosen wording, all key off a reason id that does not exist here.
  const byGoal = !reasonId && Boolean(templateType);
  const [options, setOptions] = useState<Loading<Option[]>>(undefined);
  // Same reason as the send log: `null` already means «loading» here, so «we could not read» gets
  // its own field rather than borrowing one that means something else.
  const [optionsFailed, setOptionsFailed] = useState(false);
  /** WHY the list is empty, in the server's word — «unread», «pending», «none» or empty.
   *  The screen chooses the sentence; it does not decide the cause, which is the whole defect
   *  this replaced: one reassurance about Meta shown for three unrelated states. */
  const [emptyBecause, setEmptyBecause] = useState('');
  /** Which row is open. One at a time: two bubbles side by side is the grid this replaced. */
  const [opened, setOpened] = useState('');
  /** Bumped after a save, so both reads run again — the new draft appears without a reopen. */
  const [reload, setReload] = useState(0);
  /** The shop's tone — what it sends today when it has chosen no text of its own. */
  const [tone, setTone] = useState('warm');
  /** His own approved text, when he pointed this reason at one. Empty means ours. */
  const [chosen, setChosen] = useState('');
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');
  /** The blanks THIS message can fill — the editor's whole guard rail, and the server's answer. */
  const [slots, setSlots] = useState<Slot[]>([]);
  /** The address this message owes its reader, named by the server so the editor can show
   *  it locked. WHICH one it is follows from the class alone, and that rule has one owner
   *  in `reasons.mandatory_tail` — the screen only renders what it is handed. */
  const [mandatory, setMandatory] = useState<Mandatory | undefined>(undefined);
  const [writing, setWriting] = useState(false);
  /**
   * HIS TEXTS THAT ARE NOT SENDING, and this is the half the bubbles cannot show. A draft he
   * saved, one waiting on Meta for a day, one refused — without them the editor's «حفظ» leads
   * nowhere visible, and a refusal nobody can see is a shop that quietly gives up.
   */
  const [mine, setMine] = useState<Mine[] | null>([]);
  const [help, setHelp] = useState<HelpRow[] | null>([]);
  /** THE FLOW BUTTON, OPENED FOR REAL — which option's button is being walked through (its
   *  `flow_name`), the real screens fetched for it, and either state a fetch can end in. One
   *  at a time, same discipline as `opened` above: a second bubble open beneath the first would
   *  ask which Flow a tap belongs to. */
  const [openFlow, setOpenFlow] = useState<{ name: string; flow: FlowJson } | 'loading' | null>(null);
  const [flowError, setFlowError] = useState('');
  /** THE SAME PHONE MOCKUP THE ADMIN PANEL USES (AdminWhatsAppTemplates.tsx's own "معاينة على
   *  واتساب") — which option, if any, is open in it. Additive to the compact bubble row above (he
   *  still compares wordings side by side there); this is the "show me exactly what he receives,
   *  full chrome and all" button for whichever one he wants to look closer at. */
  const [phonePreview, setPhonePreview] = useState<Option | null>(null);

  useEffect(() => {
    const id = byGoal ? 'reminders.preview_by_type' : 'reminders.preview_reason';
    const a = action(catalog, id);
    if (!a) { setOptions(DENIED); return; }
    call<{ options: Option[]; chosen?: string; tone?: string; error?: string;
           empty_because?: string;
           reason?: { slots?: Slot[]; mandatory?: Mandatory } }>(
      session, a, byGoal ? { template_type: templateType } : { reason_id: reasonId })
      .then((x) => {
        if (x.error) { setError(x.error); setOptions([]); return; }
        setOptions(x.options ?? []);
        setEmptyBecause(x.empty_because ?? '');
        setChosen(x.chosen ?? '');
        setTone(x.tone ?? 'warm');
        setSlots(x.reason?.slots ?? []);
        setMandatory(x.reason?.mandatory);
      })
      .catch(() => { setOptionsFailed(true); setOptions([]); });
  }, [session, catalog, reasonId, templateType, byGoal, reload]);

  useEffect(() => {
    // NO REASON, NO TEXTS OF HIS OWN TO LIST — see `byGoal`'s own note.
    if (byGoal) return;
    const a = action(catalog, 'reminders.my_templates');
    if (!a) return;
    call<{ templates: Mine[] }>(session, a, { reason_id: reasonId })
      .then((x) => setMine((x.templates ?? []).filter((t) => t.status !== 'approved')))
      .catch(() => setMine(null));
  }, [session, catalog, reasonId, byGoal, reload]);

  useEffect(() => {
    const a = action(catalog, 'reminders.my_template_help');
    if (!a) return;
    call<{ requests: HelpRow[] }>(session, a)
      .then((x) => setHelp(x.requests ?? []))
      // SILENT ON FAILURE, and only here: the help state DECORATES the list. A shop that cannot
      // read it still sees its drafts and both buttons.
      .catch(() => setHelp(null));
  }, [session, catalog, reload]);

  /**
   * MAKE THIS VOICE HIS (#326).
   *
   * The three bubbles have always been readable and never choosable: one carried «هذه التي
   * تُرسَل» and the other two were decoration, with a caption sending him to «حسابي» for a
   * control that was not there either. The tone lives on the tenant's branding — the same
   * record the logo and the colour live in — and `rendering.choose` has always preferred it.
   *
   * MERGED, NEVER REPLACED, and the reason is written next door in AccountPanes: `branding` is
   * a free-form record, and sending our one field alone would drop his logo and his colour.
   * So the current record is read first and the tone laid on top of it.
   */
  const chooseTone = async (next: string) => {
    const read = action(catalog, 'tenant.view_self');
    const write = action(catalog, 'tenant.update_branding');
    if (!read || !write || next === tone) return;
    setSaving(next); setError('');
    try {
      const t = await call<{ branding?: Record<string, unknown> }>(session, read);
      await call(session, write, { branding: { ...(t?.branding ?? {}), tone: next } });
      setTone(next);
      onChosen();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('messagePreview.toneSaveError'));
    } finally {
      setSaving('');
    }
  };

  const pick = async (option: Option) => {
    const a = action(catalog, 'reminders.set_reason');
    if (!a || !option.mine) return;
    setSaving(option.name); setError('');
    try {
      const out = await call<{ error?: string }>(session, a,
        { reason_id: reasonId, template: option.name });
      if (out?.error) setError(out.error);
      else { setChosen(option.name); onChosen(); }
    } catch (e) {
      setError(e instanceof Error ? e.message : t('messagePreview.saveError'));
    } finally {
      setSaving('');
    }
  };

  /**
   * TWO BUTTONS THAT DID NOT EXIST, and between them the draft had nowhere to go.
   *
   * «ارفعه» — writing was reachable and submitting was not, so «قوالبي» was a notepad: every text
   * an owner wrote sat as a draft for ever with nothing to press.
   *
   * «ساعدوني» — the cost of having no reviewer of ours between him and Meta. A refusal arrives in
   * English, from somebody he cannot reach, about a rule he has never read; without this he edits
   * a word, resubmits, is refused again, and after the third time stops using the feature.
   */
  const act = async (id: string, name: string, busyKey: string) => {
    const a = action(catalog, id);
    if (!a) return;
    setSaving(busyKey); setError('');
    try {
      const out = await call<{ ok?: boolean; error?: string }>(session, a, { name });
      if (out?.error) setError(out.error);
      else onChosen();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('messagePreview.actionError'));
    } finally {
      setSaving('');
    }
  };

  /**
   * OPEN THE REAL FLOW, not a described one. Same engine `AdminWhatsAppTemplates.tsx` uses
   * (`rj-ui/WhatsAppPreview.tsx`'s `WaFlowScreens`) — the exact screens Meta would render, fetched
   * through `operations.whatsapp_flow_json`'s shop-facing twin, never a hand-drawn stand-in.
   */
  const openFlowButton = async (flowName: string) => {
    const a = action(catalog, 'operations.whatsapp_flow_json');
    if (!a || !flowName) return;
    setFlowError('');
    setOpenFlow('loading');
    try {
      const j = await call<FlowJson>(session, a, { name: flowName });
      setOpenFlow({ name: flowName, flow: j });
    } catch (e) {
      setOpenFlow(null);
      setFlowError(e instanceof Error ? e.message : t('messagePreview.flowFetchError'));
    }
  };

  const useOurs = async () => {
    const a = action(catalog, 'reminders.set_reason');
    if (!a) return;
    setSaving('ours'); setError('');
    try {
      await call(session, a, { reason_id: reasonId, template: '' });
      setChosen('');
      onChosen();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('messagePreview.saveError'));
    } finally {
      setSaving('');
    }
  };

  // ONLY WHAT ARRIVED IS SPLIT. `undefined`, `null` and DENIED each have their own sentence
  // below; treating any of them as an empty list here is how the four states became one.
  const arrived: Option[] = isReady(options) ? options : [];
  const ours = arrived.filter((o) => !o.mine);
  const his = arrived.filter((o) => o.mine);

  return (
    <Modal open onClose={onClose} size="lg" title={label} subtitle={when}>
      <div className="flex flex-col gap-5">
        {error ? <p className="text-sm text-danger">{error}</p> : null}

        {isLoading(options) ? (
          <div className="flex flex-col gap-3">
            <Skeleton height={96} /><Skeleton height={96} />
          </div>
        ) : isDenied(options) ? (
          <p className="text-sm text-text-secondary">{t('messagePreview.noPermission')}</p>
        ) : optionsFailed || hasFailed(options) ? (
          // OURS, AND SAID SO. This sentence was already the honest one; it is now shown for the
          // failure ALONE, so the case below can say something different and true.
          <p className="text-sm text-text-secondary">
            {t('messagePreview.loadFailed')}
          </p>
        ) : !isReady(options) || options.length === 0 ? (
          /* THREE REASONS, THREE SENTENCES — and one of them used to be shown for all three.
             «القوالب تُراجَع لدى واتساب، وقد تستغرق ساعات» told him to wait for Meta even when
             nothing had ever been submitted, and even when the failure was ours: the list is built
             from OUR library, which Meta never sees. So he waited for a review that was not
             happening, about texts we ship, while the real cause went unread.
             The server names the state; this only chooses the words. */
          <p className="text-sm text-text-secondary">
            {emptyBecause === 'unread'
              ? t('messagePreview.empty.unread')
              : emptyBecause === 'pending'
                ? t('messagePreview.empty.pending')
                : t('messagePreview.empty.none')}
          </p>
        ) : (
          <>
            {/* ── ONE TABLE, AND A ROW THAT OPENS INTO THE MESSAGE ─────────────────────────
                THE QUESTION THIS ANSWERED: «مو المفروض الصيغ والرسائل تكون ظاهرة له؟ ويكون
                معها الحالات حقت واتساب؟» — the answer settled on was «الاثنان: جدولٌ يفتح فقاعة».

                WHAT IT REPLACED WAS THREE PLACES FOR ONE QUESTION. Our wordings sat in one grid
                with no standing on them at all, his APPROVED texts in a second, and everything of
                his still a draft, waiting or refused in a third section further down — so «which
                of these can actually reach my customer today» had to be assembled by the reader
                out of three layouts. A wording of his that Meta refused was reachable only by
                scrolling past the two grids that did not contain it.

                THE TABLE IS FOR SCANNING AND THE BUBBLE IS FOR READING, so neither is asked to do
                the other's job: the row carries the tone, the opening words and the standing; one
                press opens the message at full size, exactly as the customer receives it — which
                is the whole reason this screen exists and the one thing a table must not replace. */}
            <section className="flex flex-col gap-2">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium">{t('messagePreview.availableWordings')}</h3>
                <span className="text-xs text-text-secondary">
                  {t('messagePreview.tapHint')}
                </span>
              </div>

              <ul className="flex flex-col divide-y divide-border-subtle rounded-card border border-border-subtle">
                {arrived.map((o) => {
                  const state = standing(o);
                  const isOpen = opened === o.name;
                  const sending = o.mine ? chosen === o.name : !chosen && o.tone === tone;
                  return (
                    <li key={o.name} className="flex flex-col">
                      <button
                        type="button"
                        onClick={() => setOpened(isOpen ? '' : o.name)}
                        aria-expanded={isOpen}
                        className="flex items-center gap-3 px-3 py-2.5 text-right"
                      >
                        <span className="w-20 shrink-0 text-xs text-text-secondary">
                          {o.mine ? t('messagePreview.yourText') : toneLabel(t, o.tone)}
                        </span>
                        {/* THE OPENING WORDS, NOT THE WHOLE MESSAGE. A row that wraps to four
                            lines is not a row, and the full text is one press away. */}
                        <span className="min-w-0 flex-1 truncate text-sm">{o.text}</span>
                        {sending ? (
                          <Badge tone="info">
                            <Check size={12} aria-hidden className="me-1" />
                            {t('messagePreview.sendingNow')}
                          </Badge>
                        ) : null}
                        {/* NO BADGE AT ALL when we could not ask — see `standing`. */}
                        {state ? <Badge tone={state.tone}>{state.label}</Badge> : null}
                      </button>

                      {isOpen ? (
                        <div className="flex flex-col gap-3 border-t border-border-subtle bg-surface-2 px-3 py-3">
                          {/* ── THE SHAPE, THEN THE EXAMPLE ────────────────────────────
                              THE GAP THIS CLOSED: «العميل يقرا الرساله ما يعرف وين الفراغات».
                              What was here was the filled example alone — what the shop's
                              customer receives — and from it an owner cannot tell which words
                              are the shop's forever and which change with every person. Wanting
                              to write his own wording, he would have no idea where the blanks
                              belong.

                              THE BLANKS ARE NAMED, NOT NUMBERED. `{{2}}` is a customer in one
                              wording and a service in the next; the number is a position. The
                              server substitutes the meaning from the same vocabulary the editor
                              puts on its chips, so one word describes a blank everywhere. */}
                          {o.template && o.template !== o.text ? (
                            <div className="flex flex-col gap-1">
                              <span className="text-xs text-text-secondary">{t('messagePreview.templateAsWritten')}</span>
                              <p className="whitespace-pre-wrap rounded-card bg-surface-1 px-3 py-2
                                            text-sm text-text-secondary">
                                {o.template}
                              </p>
                            </div>
                          ) : null}
                          <Bubble text={o.text} caption={o.mine ? t('messagePreview.yourText') : toneLabel(t, o.tone)}
                                  buttons={o.buttons}
                                  onPressButton={(b) => { if (b.kind === 'flow' && b.flow_name) void openFlowButton(b.flow_name); }} />
                          {/* THE FLOW, OPENED FOR REAL — only for the row whose button was
                              actually pressed; a second row's bubble stays a static preview. */}
                          {(o.buttons ?? []).some((b) => b.flow_name && (openFlow === 'loading' || openFlow?.name === b.flow_name)) ? (
                            <div className="flex flex-col items-center gap-2 rounded-card border border-border-subtle bg-surface-1 p-3">
                              {openFlow === 'loading' ? (
                                <>
                                  <Skeleton height={16} width={120} />
                                  <Skeleton height={80} />
                                </>
                              ) : openFlow ? (
                                <WaFlowScreens flow={openFlow.flow} onDone={() => setOpenFlow(null)} />
                              ) : null}
                            </div>
                          ) : null}
                          {flowError && (o.buttons ?? []).some((b) => b.kind === 'flow') ? (
                            <p role="alert" className="text-xs text-danger">{flowError}</p>
                          ) : null}
                          {/* META'S OWN WORDS when it refused. Re-wording a refusal sends him
                              looking for a problem we invented. */}
                          {o.reason ? (
                            <p className="text-xs text-text-secondary">{o.reason}</p>
                          ) : null}
                          <div className="flex flex-wrap items-center gap-2">
                            {/* THE SAME MOCKUP لوحة الإدارة يستخدمها — full phone chrome (status
                                bar, WhatsApp header, wallpaper), not just the bare green bubble
                                above. */}
                            <Button variant="ghost" onClick={() => setPhonePreview(o)} className="gap-2">
                              <Eye size={14} /> {t('messagePreview.previewOnWhatsapp')}
                            </Button>
                            {sending ? (
                              <span className="text-xs text-text-secondary">
                                {t('messagePreview.thisIsSendingNote')}
                              </span>
                            ) : o.mine ? (
                              <Button variant="ghost" disabled={saving === o.name}
                                      onClick={() => pick(o)}>
                                {t('messagePreview.useIt')}
                              </Button>
                            ) : chosen ? (
                              <Button variant="ghost" disabled={saving === 'ours'}
                                      onClick={useOurs}>
                                {t('messagePreview.backToOurs')}
                              </Button>
                            ) : (
                              <Button variant="ghost" disabled={saving === o.tone}
                                      onClick={() => { void chooseTone(o.tone); }}>
                                {t('messagePreview.makeMyTone')}
                              </Button>
                            )}
                            {o.mine && o.status === 'draft'
                              && action(catalog, 'reminders.submit_template') ? (
                              <Button variant="ghost" disabled={saving === o.name}
                                      onClick={() => act('reminders.submit_template', o.name, o.name)}>
                                {t('messagePreview.submitToWhatsapp')}
                              </Button>
                            ) : null}
                            {o.mine && o.status === 'rejected'
                              && action(catalog, 'reminders.template_help') ? (
                              <Button variant="ghost" disabled={saving === `help:${o.name}`}
                                      onClick={() =>
                                        act('reminders.template_help', o.name, `help:${o.name}`)}>
                                {t('messagePreview.helpMe')}
                              </Button>
                            ) : null}
                            {/* OUR ANSWER, ON THE SCREEN HE ASKED FROM. A reply that lives only in
                                a support channel is one he cannot find the day he sits down to fix
                                the text. */}
                            {(help ?? []).find((h) => h.name === o.name)?.answer ? (
                              <span className="text-xs text-text-secondary">
                                {(help ?? []).find((h) => h.name === o.name)?.answer}
                              </span>
                            ) : (help ?? []).some((h) => h.name === o.name && h.status === 'open') ? (
                              <span className="text-xs text-text-secondary">
                                {t('messagePreview.requestReceived')}
                              </span>
                            ) : null}
                          </div>
                        </div>
                      ) : null}
                    </li>
                  );
                })}
              </ul>

              <p className="text-xs text-text-secondary">
                {chosen
                  ? t('messagePreview.footerChosen')
                  : t('messagePreview.footerTone')}
              </p>
            </section>

            {/* ── his own words, when he wants them — never for a bare goal, which has no reason
                to attach a written text to ──────────────────────────────────────────────────── */}
            {!byGoal && canRetext && action(catalog, 'reminders.write_template') ? (
              <div className="flex items-center justify-between gap-3 border-t border-border-subtle pt-4">
                <span className="text-sm text-text-secondary">
                  {t('messagePreview.writeYourOwnPrompt')}
                </span>
                <Button variant="ghost" onClick={() => setWriting(true)}>{t('messagePreview.writeYourText')}</Button>
              </div>
            ) : null}

            {writing && !byGoal ? (
              <TextEditor
                session={session}
                catalog={catalog}
                reasonId={reasonId ?? ''}
                label={label}
                slots={slots}
                mandatory={mandatory}
                // WHAT HE WROTE LAST TIME, if he wrote one. Without this the editor opened blank
                // and his saved text sat in `mine` one component away, so a second edit meant
                // typing the whole message again.
                body={(isReady(mine) ? mine : []).find((t) => t.body)?.body ?? ''}
                // AND WHICH TEXT HE IS EDITING. Without it the store rebuilt the same name and
                // wrote over the row underneath: the text Meta approved was gone, and an
                // unapproved draft inherited its approved name. The store now refuses to collide
                // whatever a caller sends — but a version that says what it replaces is the one
                // that retires the old text when the new one is approved, instead of orphaning it.
                replaces={(isReady(mine) ? mine : []).find((t) => t.body)?.name ?? ''}
                onClose={() => setWriting(false)}
                onSaved={() => { setReload((n) => n + 1); onChosen(); }}
              />
            ) : null}

            {/* WHY HE CANNOT WRITE ONE, WHEN HE CANNOT — said here rather than left to guess.
                Never for a bare goal: that sentence is about a legal right on a reason, not
                about this screen's own limits. */}
            {!byGoal && !canRetext ? (
              <p className="flex items-center gap-2 border-t border-border-subtle pt-4 text-sm text-text-secondary">
                <Lock size={14} aria-hidden />
                {t('messagePreview.cannotWriteNote')}
              </p>
            ) : null}
          </>
        )}
      </div>

      {/* THE SAME MOCKUP لوحة الإدارة يستخدمها — same engine, same chrome, same "بالضبط ما يستلمه
          العميل" promise, for whichever wording he pressed «معاينة على واتساب» on. Nested INSIDE
          this screen's own Modal on purpose — see this file's own header note on why this screen
          stays on `@base-ui/design-system/Modal`: its stacking registry is exactly what lets a
          second dialog open on top of the first without either losing Escape/focus handling. */}
      {phonePreview ? (
        <Modal open onClose={() => setPhonePreview(null)} title={t('messagePreview.previewOnWhatsapp')}
              subtitle={t('messagePreview.previewSubtitle')}>
          <WhatsAppTemplatePreview
            data={{
              // ALREADY-RESOLVED text (real example values, not `{{1}}` placeholders) — no
              // `examples` array needed, `fillPlaceholders` no-ops on a body with nothing left to
              // fill.
              body: phonePreview.text,
              flowButton: phonePreview.buttons?.find((b) => b.kind === 'flow' && b.flow_name)
                ? (() => {
                    const b = phonePreview.buttons!.find((x) => x.kind === 'flow' && x.flow_name)!;
                    return { flowName: b.flow_name!, text: b.label };
                  })()
                : undefined,
            }}
            fetchFlowJson={(flowName) => {
              const a = action(catalog, 'operations.whatsapp_flow_json');
              if (!a) return Promise.reject(new Error(t('messagePreview.noFlowPermission')));
              return call<FlowJson>(session, a, { name: flowName });
            }}
          />
        </Modal>
      ) : null}
    </Modal>
  );
}

/**
 * A WhatsApp bubble. Green-tinted, tail on the sending side, and the caption UNDER it rather than
 * inside — a label inside the bubble is text the customer never receives sitting where the text he
 * receives goes.
 */
export function Bubble({ text, caption, active, activeLabel, busy, onChoose, action: act, buttons, onPressButton }: {
  text: string;
  caption: string;
  active?: boolean;
  activeLabel?: string;
  busy?: boolean;
  /** Given only when this bubble can BECOME the shop's voice — see `chooseTone` (#326). */
  onChoose?: () => void;
  action?: React.ReactNode;
  /** See `MessageButton`'s own docstring — absent for the vast majority of messages. */
  buttons?: MessageButton[];
  /** Given only where a Flow button can actually be opened live — see `openFlowButton` above.
   *  Absent leaves the button exactly as before: a real label, not yet interactive. */
  onPressButton?: (button: MessageButton) => void;
}) {
  const { t } = useOperatorI18n();
  // THE WHOLE BUBBLE IS THE TARGET, not a button underneath it. He is choosing a sentence, and
  // the sentence is the thing on the screen — a separate «اختر» control asks him to read one
  // element and press another. A real <button> rather than a div with a handler: the keyboard,
  // the screen reader and the focus ring all come free, and this dialog is reachable by tab.
  const Tag = onChoose ? "button" : "div";
  return (
    <figure className="flex flex-col gap-2">
      <Tag
        type={onChoose ? "button" : undefined}
        onClick={onChoose}
        disabled={onChoose ? busy : undefined}
        aria-pressed={onChoose ? false : undefined}
        className={[
          // WHATSAPP'S OWN SENT-BUBBLE GREEN, FIXED — never the theme's `bg-surface-2` (owner's
          // own instruction: "خلي المثال ثابت في رسالة خضراء مثل الواتساب"). A brand colour, not a
          // semantic one — same literal `#DCF8C6`/`#111b21` pair `rj-ui/WhatsAppPreview.tsx`'s own
          // phone-mockup bubble already uses, so a shop sees the identical bubble whether it is
          // reading this one-off preview or the full interactive phone mockup.
          'relative w-full rounded-2xl rounded-ss-sm bg-[#DCF8C6] p-3 text-sm leading-relaxed text-[#111b21]',
          'text-start shadow-sm ring-1 transition',
          active
            ? 'ring-accent shadow'
            : onChoose
              ? 'ring-transparent hover:ring-accent-soft hover:shadow focus-visible:ring-accent'
              : 'ring-transparent',
          busy ? 'opacity-60' : '',
        ].join(' ')}
      >
        {text}
      </Tag>
      {/* ── THE BUTTON(S), OUTSIDE THE BUBBLE — exactly where Meta actually draws them. A
          shop owner who has never seen this rendered has no way to picture what «افتح الحجز»
          looks like next to his words: still text-only WhatsApp, or a link, or a button that
          opens our own screens without ever leaving the app (a Flow). One row per button,
          divided from the one above it — Meta's own layout for more than one. */}
      {buttons && buttons.length > 0 ? (
        <div className="flex flex-col overflow-hidden rounded-2xl ring-1 ring-border-subtle">
          {buttons.map((b, i) => {
            const Tag = onPressButton && b.kind === 'flow' && b.flow_name ? 'button' : 'div';
            return (
              <Tag
                key={`${b.label}-${i}`}
                type={Tag === 'button' ? 'button' : undefined}
                onClick={Tag === 'button' ? () => onPressButton?.(b) : undefined}
                className={[
                  'flex items-center justify-center gap-2 bg-surface-1 px-3 py-2.5 text-sm font-medium text-accent',
                  i > 0 ? 'border-t border-border-subtle' : '',
                  Tag === 'button' ? 'w-full transition hover:bg-surface-2 focus-ring' : '',
                ].join(' ')}
              >
                {b.kind === 'flow'
                  ? <Sparkles size={14} aria-hidden />
                  : <ExternalLink size={14} aria-hidden />}
                <span>{b.label}</span>
              </Tag>
            );
          })}
        </div>
      ) : null}
      <figcaption className="flex items-center justify-between gap-2 px-1">
        <span className="flex items-center gap-1 text-xs text-text-secondary">
          {active ? <Check size={14} className="text-accent" aria-hidden /> : null}
          {/* THE VOICE IS ALWAYS NAMED. The chosen one used to REPLACE its name with the label,
              so the one bubble he most wanted to identify was the one that stopped saying
              which voice it was. */}
          <span>{caption}</span>
          {active && activeLabel ? (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-accent-on-soft">
              {activeLabel}
            </span>
          ) : null}
          {busy ? <span>{t('messagePreview.savingEllipsis')}</span> : null}
        </span>
        {act}
      </figcaption>
    </figure>
  );
}
