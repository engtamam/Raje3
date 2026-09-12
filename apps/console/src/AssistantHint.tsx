/**
 * The "?" icon, backed by the assistant instead of a hardcoded sentence — Phase 5 of the
 * assistant rollout. Same shape as `Hint.tsx` on purpose (44px touch target around a quiet 24px
 * "؟", opens INLINE on tap rather than a hover tooltip a workshop tablet cannot produce) — a
 * person should not have to learn a second gesture for "explain this" just because this one's
 * text comes from a network call instead of a prop.
 *
 * INDEPENDENT ON/OFF SWITCH, DELIBERATELY SEPARATE FROM THE FUTURE CHAT WIDGET (Phase 6) — a
 * deployment may want the quick anchor lookup without the full conversational assistant, or vice
 * versa. `VITE_ASSISTANT_HELP_ICON_ENABLED` gates rendering entirely: `false` (or unset) renders
 * nothing, not even a disabled icon — a switched-off feature should leave no trace on the screen.
 *
 * WHY A CLICK, NOT ALWAYS-FETCHED. `by_anchor()` is a plain dictionary lookup with no ranking and
 * no model cost by the service's own design (see api.ts's own note) — but a screen with a dozen
 * "؟" icons must not fire a dozen requests just because it rendered. Fetching only on the tap that
 * opens it means the cost is exactly the number of times someone actually asked.
 *
 * A 404 (no authored entry yet for this anchor — expected until Phase 4 writes one) is NOT an
 * error state: it reads «ما فيه شرح لهذا بعد» in the same quiet tone `Hint.tsx` uses for anything
 * else, never a red banner over a feature that simply has not been written yet.
 */
import { useState } from 'react';
import { fetchAssistantHelp, sentenceFor, type AssistantHelpEntry } from './api';
import type { Session } from './session';
import { useOperatorI18n } from './operator-i18n';
import './assistant-hint-i18n';

type State =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'found'; entry: AssistantHelpEntry }
  | { kind: 'empty' }
  | { kind: 'error'; message: string };

export function AssistantHint({ session, anchor, label }:
    { session: Session; anchor: string; label?: string }) {
  const { t } = useOperatorI18n();
  const [state, setState] = useState<State>({ kind: 'idle' });
  const open = state.kind !== 'idle';

  // Read at RENDER time, not module load — a switched-off feature must react to its own env
  // var like every screen it sits on does, not freeze whatever value happened to exist first.
  if (import.meta.env.VITE_ASSISTANT_HELP_ICON_ENABLED !== 'true') return null;

  async function toggle() {
    if (open) { setState({ kind: 'idle' }); return; }
    setState({ kind: 'loading' });
    try {
      const entry = await fetchAssistantHelp(session, anchor);
      setState(entry ? { kind: 'found', entry } : { kind: 'empty' });
    } catch (e) {
      setState({ kind: 'error', message: sentenceFor(e, t('assistantHint.fetchFailed')) });
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label={label ?? t('assistantHint.label')}
        aria-expanded={open}
        onClick={toggle}
        // SAME 44px/24px SPLIT AS Hint.tsx — see its own comment on why the touch target and the
        // drawn shape are deliberately not the same size.
        className="grid size-11 shrink-0 place-items-center rounded-full"
      >
        <span aria-hidden className="grid size-6 place-items-center rounded-full bg-surface-2 text-xs text-text-secondary">
          {t('assistantHint.questionMark')}
        </span>
      </button>
      {state.kind === 'loading' ? (
        <p className="basis-full text-xs leading-relaxed text-text-secondary">...</p>
      ) : null}
      {state.kind === 'found' ? (
        <p className="basis-full text-xs leading-relaxed text-text-secondary">{state.entry.body}</p>
      ) : null}
      {state.kind === 'empty' ? (
        <p className="basis-full text-xs leading-relaxed text-text-secondary">{t('assistantHint.noEntry')}</p>
      ) : null}
      {state.kind === 'error' ? (
        <p className="basis-full text-xs leading-relaxed text-red-600">{state.message}</p>
      ) : null}
    </>
  );
}
