/**
 * One message, as the customer will read it — and the wordings he may choose between.
 *
 * WHY A PREVIEW AND NOT A LIST OF NAMES. «تأكيد الزيارة» is a name; «يا هلا محمد، نوّرتنا اليوم في
 * مغسلة النخيل» is the thing he is deciding about. An owner asked to pick between "brief", "warm"
 * and "formal" is being asked to imagine three messages; an owner shown three bubbles is reading.
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
import { Modal } from '@base-ui/design-system/Modal';
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { isDenied, isReady, DENIED, hasFailed, isLoading, type Loading } from '../loading';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Check, Lock } from 'lucide-react';
import { TextEditor, type Mandatory, type Slot } from './TextEditor';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Option { name: string; tone: string; text: string; mine?: boolean }

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

/** The three voices, named for an owner rather than for a library. */
const TONE: Record<string, string> = {
  brief: 'مختصرة',
  warm: 'ودّية',
  formal: 'رسمية',
};

export function MessagePreview({
  session, catalog, reasonId, label, when, canRetext, onClose, onChosen,
}: {
  session: Session;
  catalog: Catalog;
  reasonId: string;
  label: string;
  when: string;
  canRetext: boolean;
  onClose: () => void;
  onChosen: () => void;
}) {
  const [options, setOptions] = useState<Loading<Option[]>>(undefined);
  // Same reason as the send log: `null` already means «loading» here, so «we could not read» gets
  // its own field rather than borrowing one that means something else.
  const [optionsFailed, setOptionsFailed] = useState(false);
  /** Bumped after a save, so both reads run again — the new draft appears without a reopen. */
  const [reload, setReload] = useState(0);
  /** The shop's tone — what it sends today when it has chosen no text of its own. */
  const [tone, setTone] = useState('brief');
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

  useEffect(() => {
    const a = action(catalog, 'reminders.preview_reason');
    if (!a) { setOptions(DENIED); return; }
    call<{ options: Option[]; chosen?: string; tone?: string; error?: string;
           reason?: { slots?: Slot[]; mandatory?: Mandatory } }>(
      session, a, { reason_id: reasonId })
      .then((x) => {
        if (x.error) { setError(x.error); setOptions([]); return; }
        setOptions(x.options ?? []);
        setChosen(x.chosen ?? '');
        setTone(x.tone ?? 'brief');
        setSlots(x.reason?.slots ?? []);
        setMandatory(x.reason?.mandatory);
      })
      .catch(() => { setOptionsFailed(true); setOptions([]); });
  }, [session, catalog, reasonId, reload]);

  useEffect(() => {
    const a = action(catalog, 'reminders.my_templates');
    if (!a) return;
    call<{ templates: Mine[] }>(session, a, { reason_id: reasonId })
      .then((x) => setMine((x.templates ?? []).filter((t) => t.status !== 'approved')))
      .catch(() => setMine(null));
  }, [session, catalog, reasonId, reload]);

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
      setError(e instanceof Error ? e.message : 'تعذّر حفظ النبرة.');
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
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
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
      setError(e instanceof Error ? e.message : 'تعذّر التنفيذ.');
    } finally {
      setSaving('');
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
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
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
          <p className="text-sm text-text-secondary">لا يشمل دورك تحرير نصوص الرسائل.</p>
        ) : optionsFailed || hasFailed(options) ? (
          // OURS, AND SAID SO. This sentence was already the honest one; it is now shown for the
          // failure ALONE, so the case below can say something different and true.
          <p className="text-sm text-text-secondary">
            تعذّر عرض نصّ هذه الرسالة الآن — والخلل عندنا. حاول بعد قليل.
          </p>
        ) : !isReady(options) || options.length === 0 ? (
          <p className="text-sm text-text-secondary">
            لا توجد صيغة معتمدة لهذه الرسالة بعد. القوالب تُراجَع لدى واتساب، وقد تستغرق ساعات.
          </p>
        ) : (
          <>
            {/* ── ours: three voices, one chosen by his tone ─────────────────────────────── */}
            <section className="flex flex-col gap-3">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium">صيغنا</h3>
                <span className="text-xs text-text-secondary">
                  اختر نبرتك — تُطبَّق على كل رسائلك.
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {ours.map((o) => (
                  <Bubble
                    key={o.name}
                    text={o.text}
                    caption={TONE[o.tone] ?? o.tone}
                    active={!chosen && o.tone === tone}
                    activeLabel="نبرتك · تُرسَل"
                    busy={saving === o.tone}
                    onChoose={chosen || o.tone === tone ? undefined
                              : () => { void chooseTone(o.tone); }}
                  />
                ))}
              </div>
              {chosen ? (
                <p className="text-xs text-text-secondary">
                  نصّك أدناه هو ما يُرسَل الآن لهذه الرسالة — النبرة تحكم البقية.
                </p>
              ) : null}
            </section>

            {/* ── his own, when he has any approved ──────────────────────────────────────── */}
            {his.length > 0 ? (
              <section className="flex flex-col gap-3 border-t border-border-subtle pt-4">
                <h3 className="text-sm font-medium">نصوصك</h3>
                <div className="grid gap-3 sm:grid-cols-2">
                  {his.map((o) => (
                    <Bubble
                      key={o.name}
                      text={o.text}
                      caption="نصّك"
                      active={chosen === o.name}
                      activeLabel="هذه التي تُرسَل"
                      action={chosen === o.name ? null : (
                        <Button variant="ghost" disabled={saving === o.name}
                                onClick={() => pick(o)}>
                          استعملها
                        </Button>
                      )}
                    />
                  ))}
                </div>
                {chosen ? (
                  <button type="button" onClick={useOurs} disabled={saving === 'ours'}
                          className="self-start text-sm text-accent-on-soft underline disabled:opacity-50">
                    العودة إلى صياغتنا
                  </button>
                ) : null}
              </section>
            ) : null}

            {/* ── what he wrote and where it stands ─────────────────────────────────────── */}
            {(mine ?? []).length > 0 ? (
              <section className="flex flex-col gap-2 border-t border-border-subtle pt-4">
                <h3 className="text-sm font-medium">نصوصٌ لم تبدأ بعد</h3>
                <ul className="flex flex-col gap-2">
                  {(mine ?? []).map((m) => (
                    <li key={m.name}
                        className="flex flex-col gap-1 rounded-card border border-border-subtle p-3">
                      <span className="text-sm">{m.body}</span>
                      <span className="flex items-center gap-2">
                        <Badge tone={m.status === 'rejected' ? 'warning' : 'neutral'}>
                          {STATUS[m.status] ?? m.status}
                        </Badge>
                        {/* META'S OWN WORDS. Re-wording a refusal sends him looking for a problem
                            we invented. */}
                        {m.reason ? (
                          <span className="text-xs text-text-secondary">{m.reason}</span>
                        ) : null}
                      </span>
                      <div className="flex flex-wrap items-center gap-2">
                        {m.status === 'draft' && action(catalog, 'reminders.submit_template') ? (
                          <Button variant="ghost" disabled={saving === m.name}
                                  onClick={() => act('reminders.submit_template', m.name, m.name)}>
                            ارفعه إلى واتساب
                          </Button>
                        ) : null}
                        {m.status === 'rejected'
                          && action(catalog, 'reminders.template_help') ? (
                          <Button variant="ghost" disabled={saving === `help:${m.name}`}
                                  onClick={() =>
                                    act('reminders.template_help', m.name, `help:${m.name}`)}>
                            ساعدوني
                          </Button>
                        ) : null}
                        {/* OUR ANSWER, ON THE SCREEN HE ASKED FROM. A reply that lives only in a
                            support channel is one he reads once and cannot find the day he sits
                            down to fix the text. */}
                        {(help ?? []).find((h) => h.name === m.name)?.answer ? (
                          <span className="text-xs text-accent-on-soft">
                            {(help ?? []).find((h) => h.name === m.name)?.answer}
                          </span>
                        ) : (help ?? []).some((h) => h.name === m.name && h.status === 'open') ? (
                          <span className="text-xs text-text-secondary">
                            طلبك وصلنا — نرد عليك هنا.
                          </span>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {/* ── his own words, when he wants them ─────────────────────────────────────── */}
            {canRetext && action(catalog, 'reminders.write_template') ? (
              <div className="flex items-center justify-between gap-3 border-t border-border-subtle pt-4">
                <span className="text-sm text-text-secondary">
                  تبي صياغتك أنت؟ اكتبها ونرفعها لواتساب باسمك.
                </span>
                <Button variant="ghost" onClick={() => setWriting(true)}>اكتب نصّك</Button>
              </div>
            ) : null}

            {writing ? (
              <TextEditor
                session={session}
                catalog={catalog}
                reasonId={reasonId}
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

            {/* WHY HE CANNOT WRITE ONE, WHEN HE CANNOT — said here rather than left to guess. */}
            {!canRetext ? (
              <p className="flex items-center gap-2 border-t border-border-subtle pt-4 text-sm text-text-secondary">
                <Lock size={14} aria-hidden />
                هذه الرسالة تُرسَل بصياغتنا — نصّها مرتبط بحقٍّ نظامي لعميلك.
              </p>
            ) : null}
          </>
        )}
      </div>
    </Modal>
  );
}

/**
 * A WhatsApp bubble. Green-tinted, tail on the sending side, and the caption UNDER it rather than
 * inside — a label inside the bubble is text the customer never receives sitting where the text he
 * receives goes.
 */
function Bubble({ text, caption, active, activeLabel, busy, onChoose, action: act }: {
  text: string;
  caption: string;
  active?: boolean;
  activeLabel?: string;
  busy?: boolean;
  /** Given only when this bubble can BECOME the shop's voice — see `chooseTone` (#326). */
  onChoose?: () => void;
  action?: React.ReactNode;
}) {
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
          'relative w-full rounded-2xl rounded-ss-sm bg-accent-soft p-3 text-sm leading-relaxed',
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
      <figcaption className="flex items-center justify-between gap-2 px-1">
        <span className="flex items-center gap-1 text-xs text-text-secondary">
          {active ? <Check size={14} className="text-accent-on-soft" aria-hidden /> : null}
          {/* THE VOICE IS ALWAYS NAMED. The chosen one used to REPLACE its name with the label,
              so the one bubble he most wanted to identify was the one that stopped saying
              which voice it was. */}
          <span>{caption}</span>
          {active && activeLabel ? (
            <span className="rounded-full bg-accent-soft px-2 py-0.5 text-accent-on-soft">
              {activeLabel}
            </span>
          ) : null}
          {busy ? <span>يُحفظ…</span> : null}
        </span>
        {act}
      </figcaption>
    </figure>
  );
}
