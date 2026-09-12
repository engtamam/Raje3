/**
 * «الدعم الفني» — راجع، not the marketer's own tickets screen (apps/console/src/affiliates/
 * AffiliateTools.tsx's ShopTicketList): that one is a MARKETER reading a shop's tickets under a
 * consent grant; this one is the SHOP OWNER raising his own, straight against ticket-service's
 * ordinary tenant-scoped API (`tickets.self` — platform/services/ticket-service/app/user_actions.py).
 * Closes the loop that screen only served half of: a shop with a problem had no way to actually
 * raise one — the affiliate carousel had nothing to show until this existed.
 *
 * FAST, ON PURPOSE. One screen, one form up top (never buried behind a second tap), the open ones
 * first — the same "what needs me right now" ordering the affiliate portal's own carousel uses.
 * A shop owner reaching for support is already interrupted; this is not the place for a wizard.
 */
import { useEffect, useState, type FormEvent } from 'react';
import { LifeBuoy, Send } from 'lucide-react';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { EmptyState } from '../rj-ui/EmptyState';
import { Field, Input, Textarea } from '../rj-ui/Field';
import { PageHeader } from '../rj-ui/PageHeader';
import { Segmented } from '../rj-ui/Segmented';
import { Waiting } from '../Waiting';
import { AssistantHint } from '../AssistantHint';
import { AssistantChat } from '../AssistantChat';
import { isLoading, isReady, type Loading } from '../loading';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { useOperatorI18n } from '../operator-i18n';
import './support-i18n';

const CHAT_ENABLED = () => import.meta.env.VITE_ASSISTANT_CHAT_ENABLED === 'true';

interface Ticket {
  id?: string; subject?: string; body?: string; status?: string; type?: string;
  created_at?: number;
}

const STATUS_TONE: Record<string, 'danger' | 'warning' | 'info' | 'neutral'> = {
  new: 'danger', open: 'danger', pending: 'warning', triaged: 'warning',
  in_progress: 'info', waiting_customer: 'warning',
};

export function SupportScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { t } = useOperatorI18n();
  const [tickets, setTickets] = useState<Loading<Ticket[]>>();
  const [error, setError] = useState('');
  // «خدمة العملاء» IS THE DEFAULT WHEN IT EXISTS — self-serve first, the same ordering the product
  // owner asked for; a shop with the chat off never sees a tab bar at all, only the tickets form
  // it already had (an off feature must leave no trace on the screen).
  const [tab, setTab] = useState<'chat' | 'tickets'>(CHAT_ENABLED() ? 'chat' : 'tickets');

  const mineAction = action(catalog, 'tickets.mine');
  const openAction = action(catalog, 'tickets.open');

  const load = () => {
    if (!mineAction) return;
    call<{ tickets: Ticket[] }>(session, mineAction)
      .then((r) => setTickets(r.tickets))
      .catch(() => setError(t('support.loadFailed')));
  };
  useEffect(load, [session, catalog]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <PageHeader icon={LifeBuoy} title={t('support.title')} />

      {CHAT_ENABLED() ? (
        <Segmented
          className="grid w-full grid-cols-2 gap-1 [&>button]:w-full [&>button]:truncate"
          ariaLabel={t('support.tabsAriaLabel')}
          value={tab}
          onChange={(v) => setTab(v as typeof tab)}
          options={[
            { value: 'chat', label: t('support.tab.chat') },
            { value: 'tickets', label: t('support.tab.tickets') },
          ]}
        />
      ) : null}

      {tab === 'chat' && CHAT_ENABLED() ? (
        <AssistantChat session={session} surface="shop" />
      ) : (
        <>
          {openAction ? <NewTicketForm session={session} openAction={openAction} onSent={load} /> : null}

          {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}

          {isLoading(tickets) ? (
            <Waiting what={t('support.waitingTickets')} />
          ) : isReady(tickets) ? (
            tickets.length === 0 ? (
              <EmptyState title={t('support.emptyTitle')} description={t('support.emptyDesc')} />
            ) : (
              <ul className="flex flex-col gap-2">
                {tickets.map((tk, i) => (
                  <li key={tk.id ?? i}
                     className="flex items-center justify-between gap-3 rounded-card bg-surface-1 px-4 py-3 shadow-sm">
                    <div className="flex min-w-0 flex-col">
                      <span className="truncate font-medium">{tk.subject || tk.type || t('support.defaultTicketTitle')}</span>
                      {tk.body ? <span className="truncate text-sm text-text-secondary">{tk.body}</span> : null}
                    </div>
                    {tk.status ? (
                      <span className="flex items-center gap-1">
                        <Badge tone={STATUS_TONE[tk.status.toLowerCase()] ?? 'neutral'}>{tk.status}</Badge>
                        <AssistantHint anchor="support.ticket_status" session={session} />
                      </span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )
          ) : null}
        </>
      )}
    </div>
  );
}

function NewTicketForm({ session, openAction, onSent }: {
  session: Session; openAction: NonNullable<ReturnType<typeof action>>; onSent: () => void;
}) {
  const { t } = useOperatorI18n();
  const [type, setType] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [sent, setSent] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!type.trim() || !subject.trim()) {
      setError(t('support.form.validation'));
      return;
    }
    setBusy(true); setError('');
    try {
      await call(session, openAction, { type, subject, body });
      setType(''); setSubject(''); setBody(''); setSent(true);
      onSent();
      setTimeout(() => setSent(false), 3000);
    } catch {
      setError(t('support.form.submitFailed'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3 rounded-card bg-surface-1 p-5 shadow-sm">
      <h2 className="text-lg">{t('support.form.title')}</h2>

      <Field label={t('support.form.typeLabel')} required htmlFor="sup-type">
        <Input id="sup-type" value={type} onChange={(e) => { setType(e.target.value); setError(''); }}
              placeholder={t('support.form.typePlaceholder')} />
      </Field>

      <Field label={t('support.form.subjectLabel')} required htmlFor="sup-subject">
        <Input id="sup-subject" value={subject}
              onChange={(e) => { setSubject(e.target.value); setError(''); }}
              placeholder={t('support.form.subjectPlaceholder')} />
      </Field>

      <Field label={t('support.form.bodyLabel')} htmlFor="sup-body">
        <Textarea id="sup-body" rows={4} value={body} onChange={(e) => setBody(e.target.value)}
                 placeholder={t('support.form.bodyPlaceholder')} />
      </Field>

      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
      {sent ? <p className="text-sm text-success">{t('support.form.sent')}</p> : null}

      <Button type="submit" disabled={busy || !type.trim() || !subject.trim()}
             className="flex items-center justify-center gap-2">
        <Send size={16} aria-hidden /> {busy ? t('support.form.sending') : t('support.form.submit')}
      </Button>
    </form>
  );
}
