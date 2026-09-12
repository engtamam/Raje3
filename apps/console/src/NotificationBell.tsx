/**
 * The bell icon, in the rail — its own gold treatment on purpose (index.css's own
 * `.notification-bell`/`.notification-panel`, a second deliberate use of the gold accent this
 * product already speaks for «بوت خدمة العملاء الذكي», not the reserved full-card look). Opens a
 * glass panel listing the account's own in-app feed (`api.ts::listNotifications`) — any of our
 * services can have written an item into it via notification-service's own `POST /internal/notify`
 * (channel=inapp); this component neither knows nor cares which one did.
 *
 * NO SEVERITY, NO ICON PER ITEM, NO ACTION LINK — because `InAppItem` (the real stored shape on
 * notification-service's side) carries only `id`/`title`/`body`/`read`/`ts`. A richer per-item
 * shape was in an earlier design pass; this renders exactly what the backend actually sends,
 * clearly and well, rather than inventing fields that would silently read as blank forever.
 *
 * FETCHED ON MOUNT (for the badge count) AND AGAIN EVERY TIME THE PANEL OPENS — no polling while
 * closed. An operator does not need his badge to update mid-shift to the second; he needs it
 * accurate the moment he looks, which "fetch on mount + fetch on open" already gives him.
 */
import { useEffect, useRef, useState } from 'react';
import { Bell } from 'lucide-react';
import { listNotifications, markNotificationRead, type NotificationItem } from './api';
import type { Session } from './session';
import { tf, useOperatorI18n } from './operator-i18n';
import './notification-bell-i18n';

type Status = 'idle' | 'loading' | 'error';

function ago(ts: string, t: (key: string) => string): string {
  const then = new Date(ts).getTime();
  if (Number.isNaN(then)) return '';
  const minutes = Math.floor((Date.now() - then) / 60_000);
  if (minutes < 1) return t('notificationBell.ago.justNow');
  if (minutes < 60) return tf(t, 'notificationBell.ago.minutesAgo', { n: minutes });
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return tf(t, 'notificationBell.ago.hoursAgo', { n: hours });
  const days = Math.floor(hours / 24);
  if (days === 1) return t('notificationBell.ago.yesterday');
  return tf(t, 'notificationBell.ago.daysAgo', { n: days });
}

export function NotificationBell({ session }: { session: Session }) {
  const { t } = useOperatorI18n();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<NotificationItem[] | null>(null);
  const [status, setStatus] = useState<Status>('idle');
  const wrapRef = useRef<HTMLDivElement>(null);

  const load = () => {
    setStatus('loading');
    listNotifications(session)
      .then((rows) => { setItems(rows); setStatus('idle'); })
      .catch(() => setStatus('error'));
  };

  // Once on mount, for the badge — never repeated on a timer, see this file's own header note.
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!open) return;
    function onOutside(e: MouseEvent) {
      if (wrapRef.current && !wrapRef.current.contains(e.target as Node)) setOpen(false);
    }
    function onEscape(e: KeyboardEvent) { if (e.key === 'Escape') setOpen(false); }
    document.addEventListener('mousedown', onOutside);
    document.addEventListener('keydown', onEscape);
    return () => {
      document.removeEventListener('mousedown', onOutside);
      document.removeEventListener('keydown', onEscape);
    };
  }, [open]);

  function toggle() {
    const next = !open;
    setOpen(next);
    if (next) load();
  }

  async function markOne(id: string) {
    // OPTIMISTIC — the same "the fact is real regardless of whether the notice lands" posture
    // this whole feature already holds (rating_alerts.py's own docstring, backend side): a failed
    // mark-read must not leave the item looking unread forever if the click plainly registered.
    setItems((cur) => cur?.map((it) => (it.id === id ? { ...it, read: true } : it)) ?? cur);
    try { await markNotificationRead(session, id); } catch { /* best-effort, see above */ }
  }

  async function markAll() {
    const unread = (items ?? []).filter((it) => !it.read);
    setItems((cur) => cur?.map((it) => ({ ...it, read: true })) ?? cur);
    await Promise.all(unread.map((it) => markNotificationRead(session, it.id).catch(() => {})));
  }

  const unreadCount = (items ?? []).filter((it) => !it.read).length;

  return (
    <div ref={wrapRef} className="relative">
      <button
        type="button"
        onClick={toggle}
        aria-label={t('notificationBell.label')}
        aria-expanded={open}
        className="notification-bell"
      >
        <Bell size={20} strokeWidth={1.8} aria-hidden />
        {unreadCount > 0 ? (
          <span className="notification-bell__badge" aria-hidden>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label={t('notificationBell.title')}
          className="notification-panel absolute z-50 mt-2 w-[22rem] max-w-[calc(100vw-2rem)] rounded-2xl start-0 sm:start-auto sm:end-0"
        >
          <div className="flex items-center justify-between gap-2 border-b border-white/10 px-4 py-3">
            <h2 className="m-0 text-base font-bold">{t('notificationBell.title')}</h2>
            {unreadCount > 0 ? (
              <button type="button" onClick={markAll} className="text-xs font-medium opacity-70 hover:opacity-100">
                {t('notificationBell.markAllRead')}
              </button>
            ) : null}
          </div>

          <div className="max-h-[26rem] overflow-y-auto p-2">
            {status === 'loading' && !items ? (
              <p className="px-3 py-6 text-center text-sm opacity-70">…</p>
            ) : null}
            {status === 'error' ? (
              <p className="px-3 py-6 text-center text-sm text-danger">{t('notificationBell.loadFailed')}</p>
            ) : null}
            {status === 'idle' && items && items.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm opacity-70">{t('notificationBell.empty')}</p>
            ) : null}
            {items?.map((it) => (
              <article
                key={it.id}
                className={`relative m-1 rounded-2xl border border-white/5 bg-white/[0.03] p-3 ${it.read ? 'opacity-60' : 'notification-panel__unread'}`}
              >
                <button
                  type="button"
                  onClick={() => !it.read && markOne(it.id)}
                  className="block w-full text-start"
                >
                  <div className="flex items-center justify-between gap-2">
                    <h3 className="m-0 text-sm font-bold">{it.title}</h3>
                    {!it.read ? (
                      <span aria-hidden className="size-1.5 shrink-0 rounded-full bg-[#d4af37]" />
                    ) : null}
                  </div>
                  <p className="mb-1.5 mt-1 text-xs leading-relaxed opacity-90">{it.body}</p>
                  <span className="text-[11px] opacity-60">{ago(it.ts, t)}</span>
                </button>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  );
}
