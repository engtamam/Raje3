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
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';

interface Option { name: string; tone: string; text: string; mine?: boolean }

/** The three voices, named for an owner rather than for a library. */
const TONE: Record<string, string> = {
  brief: 'مختصرة',
  warm: 'ودّية',
  formal: 'رسمية',
};

export function MessagePreview({
  session, catalog, triggerId, label, when, canRetext, onClose, onChosen,
}: {
  session: Session;
  catalog: Catalog;
  triggerId: string;
  label: string;
  when: string;
  canRetext: boolean;
  onClose: () => void;
  onChosen: () => void;
}) {
  const [options, setOptions] = useState<Option[] | null>(null);
  /** The shop's tone — what it sends today when it has chosen no text of its own. */
  const [tone, setTone] = useState('brief');
  /** His own approved text, when he pointed this trigger at one. Empty means ours. */
  const [chosen, setChosen] = useState('');
  const [saving, setSaving] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    const a = action(catalog, 'reminders.preview_trigger');
    if (!a) { setOptions([]); return; }
    call<{ options: Option[]; chosen?: string; tone?: string; error?: string }>(
      session, a, { trigger_id: triggerId })
      .then((x) => {
        if (x.error) { setError(x.error); setOptions([]); return; }
        setOptions(x.options ?? []);
        setChosen(x.chosen ?? '');
        setTone(x.tone ?? 'brief');
      })
      .catch(() => setOptions([]));
  }, [session, catalog, triggerId]);

  const pick = async (option: Option) => {
    const a = action(catalog, 'reminders.set_trigger');
    if (!a || !option.mine) return;
    setSaving(option.name); setError('');
    try {
      const out = await call<{ error?: string }>(session, a,
        { trigger_id: triggerId, template: option.name });
      if (out?.error) setError(out.error);
      else { setChosen(option.name); onChosen(); }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'تعذّر الحفظ.');
    } finally {
      setSaving('');
    }
  };

  const useOurs = async () => {
    const a = action(catalog, 'reminders.set_trigger');
    if (!a) return;
    setSaving('ours'); setError('');
    try {
      await call(session, a, { trigger_id: triggerId, template: '' });
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
