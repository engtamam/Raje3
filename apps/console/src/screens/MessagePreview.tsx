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
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Check, Lock } from 'lucide-react';
import { TextEditor, type Slot } from './TextEditor';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Option { name: string; tone: string; text: string; mine?: boolean }

/** One of his own texts that is not sending yet — and why it is not. */
interface Mine { name: string; status: string; reason?: string; body: string }

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
  const [options, setOptions] = useState<Option[] | null>(null);
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
  const [writing, setWriting] = useState(false);
  /**
   * HIS TEXTS THAT ARE NOT SENDING, and this is the half the bubbles cannot show. A draft he
   * saved, one waiting on Meta for a day, one refused — without them the editor's «حفظ» leads
   * nowhere visible, and a refusal nobody can see is a shop that quietly gives up.
   */
  const [mine, setMine] = useState<Mine[]>([]);

  useEffect(() => {
    const a = action(catalog, 'reminders.preview_reason');
    if (!a) { setOptions([]); return; }
    call<{ options: Option[]; chosen?: string; tone?: string; error?: string;
           reason?: { slots?: Slot[] } }>(
      session, a, { reason_id: reasonId })
      .then((x) => {
        if (x.error) { setError(x.error); setOptions([]); return; }
        setOptions(x.options ?? []);
        setChosen(x.chosen ?? '');
        setTone(x.tone ?? 'brief');
        setSlots(x.reason?.slots ?? []);
      })
      .catch(() => setOptions([]));
  }, [session, catalog, reasonId, reload]);

  useEffect(() => {
    const a = action(catalog, 'reminders.my_templates');
    if (!a) return;
    call<{ templates: Mine[] }>(session, a, { reason_id: reasonId })
      .then((x) => setMine((x.templates ?? []).filter((t) => t.status !== 'approved')))
      .catch(() => setMine([]));
  }, [session, catalog, reasonId, reload]);

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

  const ours = (options ?? []).filter((o) => !o.mine);
  const his = (options ?? []).filter((o) => o.mine);

  return (
    <Modal open onClose={onClose} size="lg" title={label} subtitle={when}>
      <div className="flex flex-col gap-5">
        {error ? <p className="text-sm text-danger">{error}</p> : null}

        {options === null ? (
          <div className="flex flex-col gap-3">
            <Skeleton height={96} /><Skeleton height={96} />
          </div>
        ) : options.length === 0 ? (
          <p className="text-sm text-text-secondary">
            تعذّر عرض نصّ هذه الرسالة الآن. حاول بعد قليل.
          </p>
        ) : (
          <>
            {/* ── ours: three voices, one chosen by his tone ─────────────────────────────── */}
            <section className="flex flex-col gap-3">
              <div className="flex items-baseline justify-between gap-2">
                <h3 className="text-sm font-medium">صيغنا</h3>
                <span className="text-xs text-text-secondary">
                  نبرتك تختار واحدة منها لكل رسائلك — تُغيَّر من «حسابي».
                </span>
              </div>
              <div className="grid gap-3 sm:grid-cols-3">
                {ours.map((o) => (
                  <Bubble
                    key={o.name}
                    text={o.text}
                    caption={TONE[o.tone] ?? o.tone}
                    active={!chosen && o.tone === tone}
                    activeLabel="هذه التي تُرسَل"
                  />
                ))}
              </div>
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
            {mine.length > 0 ? (
              <section className="flex flex-col gap-2 border-t border-border-subtle pt-4">
                <h3 className="text-sm font-medium">نصوصٌ لم تبدأ بعد</h3>
                <ul className="flex flex-col gap-2">
                  {mine.map((m) => (
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
function Bubble({ text, caption, active, activeLabel, action: act }: {
  text: string;
  caption: string;
  active?: boolean;
  activeLabel?: string;
  action?: React.ReactNode;
}) {
  return (
    <figure className="flex flex-col gap-2">
      <div
        className={[
          'relative rounded-2xl rounded-ss-sm bg-accent-soft p-3 text-sm leading-relaxed',
          'shadow-sm ring-1',
          active ? 'ring-accent' : 'ring-transparent',
        ].join(' ')}
      >
        {text}
      </div>
      <figcaption className="flex items-center justify-between gap-2 px-1">
        <span className="flex items-center gap-1 text-xs text-text-secondary">
          {active ? <Check size={14} className="text-accent-on-soft" aria-hidden /> : null}
          {active && activeLabel ? activeLabel : caption}
        </span>
        {act}
      </figcaption>
    </figure>
  );
}
