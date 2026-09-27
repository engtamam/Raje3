/**
 * «خدمة العملاء» — Phase 6: the real chat, next to «الدعم الفني» inside the same screen (product
 * owner's own design: self-serve first, human ticket escalation second — see Support.tsx).
 *
 * A TYPED QUESTION, RANKED AND ANSWERED — the OTHER read path from AssistantHint.tsx's anchor
 * lookup. `POST /ask` (app/api/v1/assistant.py) ranks against the whole KB and either answers
 * grounded-and-cited or abstains honestly; it never invents past what the KB actually says.
 *
 * STATELESS PER TURN ON THE SERVER'S OWN DESIGN (AskIn carries only `question`, no
 * conversation_id) — this screen keeps the running back-and-forth in local state only. The server
 * still records each turn (assistant.message_attributed) independently of what this screen shows,
 * so history exists even though this screen does not fetch it.
 *
 * INDEPENDENT ON/OFF SWITCH, SEPARATE FROM THE "?" ICON'S OWN — a deployment may want one without
 * the other (see AssistantHint.tsx's identical reasoning).
 */
import { useRef, useState } from 'react';
import { Send } from 'lucide-react';
import { Button } from './rj-ui/Button';
import { Card } from './rj-ui/Card';
import { Input } from './rj-ui/Field';
import { askAssistant, sentenceFor, type AssistantAnswer } from './api';
import type { Session } from './session';
import { useOperatorI18n } from './operator-i18n';
import './assistant-chat-i18n';

interface Turn {
  question: string;
  answer?: AssistantAnswer;
  error?: string;
  pending?: boolean;
}

export function AssistantChat({ session, surface }: { session: Session; surface: string }) {
  const { t } = useOperatorI18n();
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState('');
  const listEnd = useRef<HTMLDivElement>(null);

  if (import.meta.env.VITE_ASSISTANT_CHAT_ENABLED !== 'true') return null;

  async function send() {
    const q = question.trim();
    if (!q) return;
    setQuestion('');
    setTurns((cur) => [...cur, { question: q, pending: true }]);
    try {
      const answer = await askAssistant(session, q, surface);
      setTurns((cur) => cur.map((turn, i) => (i === cur.length - 1 ? { question: q, answer } : turn)));
    } catch (e) {
      const error = sentenceFor(e, t('assistantChat.sendFailed'));
      setTurns((cur) => cur.map((turn, i) => (i === cur.length - 1 ? { question: q, error } : turn)));
    } finally {
      // FEATURE-DETECTED, NOT ASSUMED — jsdom (this file's own test environment) has no
      // scrollIntoView at all, and a real browser missing it must not crash the whole send.
      requestAnimationFrame(() => listEnd.current?.scrollIntoView?.({ behavior: 'smooth' }));
    }
  }

  return (
    <Card className="flex flex-col gap-3 p-4">
      <p className="text-sm text-text-secondary">
        {t('assistantChat.intro')}
      </p>

      <div className="flex max-h-[60vh] flex-col gap-3 overflow-y-auto">
        {turns.length === 0 ? (
          <p className="text-sm text-text-muted">{t('assistantChat.emptyPrompt')}</p>
        ) : null}
        {turns.map((turn, i) => (
          <div key={i} className="flex flex-col gap-1">
            <div className="self-end rounded-2xl bg-accent px-3 py-2 text-sm text-accent-contrast">
              {turn.question}
            </div>
            {turn.pending ? (
              <div className="self-start rounded-2xl border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-text-secondary">
                ...
              </div>
            ) : turn.error ? (
              <div className="self-start rounded-2xl border border-border-subtle bg-surface-1 px-3 py-2 text-sm text-danger">
                {turn.error}
              </div>
            ) : turn.answer ? (
              <div className="flex max-w-[85%] flex-col gap-1 self-start rounded-2xl border border-border-subtle bg-surface-1 px-3 py-2 text-sm">
                <span>{turn.answer.answer}</span>
                {turn.answer.actions.length > 0 ? (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {turn.answer.actions.map((a) => (
                      <span key={a.id} className="rounded-full bg-surface-3 px-2 py-0.5 text-xs text-text-secondary">
                        {a.label}
                      </span>
                    ))}
                  </div>
                ) : null}
              </div>
            ) : null}
          </div>
        ))}
        <div ref={listEnd} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); void send(); }}
        className="flex items-center gap-2"
      >
        <Input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={t('assistantChat.inputPlaceholder')}
          aria-label={t('assistantChat.inputAriaLabel')}
        />
        <Button type="submit" disabled={!question.trim()} className="flex items-center gap-1">
          <Send size={16} aria-hidden /> {t('assistantChat.send')}
        </Button>
      </form>
    </Card>
  );
}
