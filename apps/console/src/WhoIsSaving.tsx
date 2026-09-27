/**
 * «من يحفظ؟» — the four digits that put a name on the visit.
 *
 * WHY IT OPENS AT ALL (أ-2). The visit door has always accepted `operator_id`, `/verify-pin` has
 * always been able to prove one, and nothing has ever joined them: every visit taken on a phone
 * was filed against nobody, and `_branch_for` reads that field to decide which BRANCH the work
 * belongs to. So the branch table was zeros, `last_branch_id` was never written, and the points
 * ledger had no actor.
 *
 * IT IS A PROMPT, NOT A GATE. «تخطّي» saves the visit with no operator on it, and that is a real
 * answer rather than a loophole: a shop with no PINs set must not be unable to record work, and a
 * technician with a customer waiting must never be held by a screen. What is refused is a name
 * without proof — an empty attribution is honest, a wrong one moves a shop's numbers.
 *
 * THE PICKING IS SKIPPED WHEN WE KNOW HIM. The proof expires every five minutes; asking him to
 * find his own name in a list that often is the way to make him tap «تخطّي» every time.
 */
import { useEffect, useState } from 'react';
import { Modal } from './rj-ui/Modal';
import { Button } from './rj-ui/Button';
import { listOperators, verifyPin, type FieldOperator } from './api';
import { lastSeen, remember } from './operator';
import type { Session } from './session';
import { digitsOnly } from './digits';
import { useOperatorI18n } from './operator-i18n';
import './who-is-saving-i18n';

export function WhoIsSaving({
  session, open, onProved, onSkip,
}: {
  session: Session;
  open: boolean;
  onProved: () => void;
  /** He chose to save without an operator, or there is nobody who could prove one. */
  onSkip: () => void;
}) {
  const { t } = useOperatorI18n();
  const [people, setPeople] = useState<FieldOperator[] | null | undefined>(undefined);
  const [picked, setPicked] = useState(lastSeen()?.id ?? '');
  const [pin, setPin] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!open) return;
    let live = true;
    setPin(''); setError('');
    listOperators(session)
      .then((rows) => { if (live) setPeople(rows); })
      // NULL IS «WE COULD NOT ASK», not «nobody works here» — and the sheet says so rather than
      // showing an empty list, which would read as a shop with no staff.
      .catch(() => { if (live) setPeople(null); });
    return () => { live = false; };
  }, [open, session]);

  if (!open) return null;

  // NOBODY CAN PROVE ANYTHING HERE: no operators, or none with a PIN. Asking would be theatre, so
  // the visit goes through unattributed and the sheet never appears again this press.
  if (people !== undefined && people !== null && people.length === 0) {
    onSkip();
    return null;
  }

  const submit = async () => {
    if (pin.length !== 4 || !picked) return;
    setBusy(true); setError('');
    try {
      const out = await verifyPin(session, picked, pin);
      const name = people?.find((p) => p.id === picked)?.name ?? out.operator?.name ?? '';
      remember(picked, name, out.ticket, out.ticket_ttl);
      onProved();
    } catch {
      // ONE SENTENCE FOR EVERY REFUSAL, because the server gives one on purpose: «wrong PIN»,
      // «no such operator» and «deactivated» are deliberately indistinguishable there, and
      // inventing three here would undo that.
      setError(t('whoIsSaving.wrongPin'));
      setPin('');
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal open onClose={onSkip} size="md" title={t('whoIsSaving.title')}
           subtitle={t('whoIsSaving.subtitle')}>
      <div className="flex flex-col gap-4">
        {people === null ? (
          <p className="text-sm text-text-secondary">{t('whoIsSaving.readFailed')}</p>
        ) : people === undefined ? (
          <p className="text-sm text-text-secondary">…</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {people.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => { setPicked(p.id); setError(''); }}
                className={`rounded-full border px-3 py-1.5 text-sm ${
                  picked === p.id
                    ? 'border-accent bg-accent-soft text-accent-on-soft'
                    : 'border-border-subtle bg-surface-1'}`}
              >
                {p.name}
              </button>
            ))}
          </div>
        )}

        <input
          value={pin}
          // HIS OWN PIN, ON THE FIELD SCREEN, WITH A CUSTOMER WAITING. `/\D/` is `[^0-9]` in
          // JavaScript, so an Arabic keyboard's digits were deleted as he typed them and the box
          // stayed empty with nothing to read and nothing to fix.
          onChange={(e) => setPin(digitsOnly(e.target.value).slice(0, 4))}
          inputMode="numeric"
          autoComplete="off"
          type="password"
          aria-label={t('whoIsSaving.pinAriaLabel')}
          dir="ltr"
          className="rounded-card border border-border-subtle bg-surface-1 p-3 text-center text-2xl tracking-[0.5em]"
        />

        {error ? <p className="text-sm text-danger">{error}</p> : null}

        <div className="flex items-center justify-between gap-3">
          {/* NEVER A DEAD END. He is standing in front of a customer. */}
          <Button variant="ghost" onClick={onSkip}>{t('whoIsSaving.skip')}</Button>
          <Button onClick={submit} disabled={busy || pin.length !== 4 || !picked}>{t('whoIsSaving.confirm')}</Button>
        </div>
      </div>
    </Modal>
  );
}
