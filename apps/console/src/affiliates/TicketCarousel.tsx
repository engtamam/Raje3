/**
 * تذاكر المحلات، كبانر واحد يُقلَّب — Home's own carousel over `open_tickets`.
 *
 * WHY A CAROUSEL AND NOT A LIST. The tickets screen already has a full list (AffiliateTools.tsx's
 * own `ShopTicketList`) — this widget is not a second copy of it, it is Home's own "who needs you
 * right now" surface, and a list of N rows competes for the same vertical space `UrgentLeadsCard`
 * and `EarningsCard` already win by the research this screen is built on (see AffiliateHome.tsx's
 * own header note). One card at a time keeps the same footprint regardless of how many tickets are
 * open — three or thirty read the same height — while still making every single one reachable: a
 * swipe or an arrow tap, never a scroll.
 *
 * TOUCH-DRIVEN, WITH A BUTTON FALLBACK FOR EVERYONE ELSE. Pointer Events (not separate touch/mouse
 * handlers) cover finger, mouse-drag and pen in one path. The arrows exist for a mouse user who
 * never thinks to drag, and for accessibility — both are always visible, never revealed only on
 * hover, which a touch screen can never trigger.
 *
 * RTL-AWARE, WITHOUT FIGHTING IT. A flex row's child order flips under the document's own RTL,
 * which would make `translateX` math fight the reading direction the moment it's combined with an
 * index. Rather than hand-deriving a mirrored sign for every drag/arrow interaction, the sliding
 * TRACK is forced `dir="ltr"` (ordinary carousel math: index 0 first, drag-left = forward) while
 * each SLIDE keeps `dir="rtl"` so its own Arabic content still reads right-to-left — the direction
 * override is scoped to layout math, never to text.
 */
import { useRef, useState } from 'react';
import { ChevronLeft, ChevronRight, LifeBuoy } from 'lucide-react';
import type { HomeTicket } from './api';

const STATUS_TONE: Record<string, string> = {
  open: 'bg-danger-soft text-danger',
  new: 'bg-danger-soft text-danger',
  pending: 'bg-warning-soft text-warning',
  triaged: 'bg-warning-soft text-warning',
  in_progress: 'bg-info-soft text-info',
};

function statusTone(status: string): string {
  return STATUS_TONE[status.toLowerCase()] ?? 'bg-surface-2 text-text-secondary';
}

/** A ROUGH "منذ..." — good enough for a banner glance, never claimed as precise. `created_at` is
 *  unix seconds, same unit every other epoch field in this API uses. */
function timeAgo(createdAt: number | undefined): string {
  if (!createdAt) return '';
  const seconds = Math.max(0, Math.floor(Date.now() / 1000) - createdAt);
  if (seconds < 3600) return `منذ ${Math.max(1, Math.floor(seconds / 60))} دقيقة`;
  if (seconds < 86400) return `منذ ${Math.floor(seconds / 3600)} ساعة`;
  return `منذ ${Math.floor(seconds / 86400)} يوم`;
}

export function TicketCarousel({ tickets, onOpen }: {
  tickets: HomeTicket[]; onOpen: (ticket: HomeTicket) => void;
}) {
  const [index, setIndex] = useState(0);
  const dragFrom = useRef<number | null>(null);
  const dragged = useRef(false);

  if (tickets.length === 0) return null;
  const at = Math.min(index, tickets.length - 1);
  const ticket = tickets[at]!;

  const go = (delta: number) => setIndex((i) => (i + delta + tickets.length) % tickets.length);

  function onPointerDown(e: React.PointerEvent) {
    dragFrom.current = e.clientX;
    dragged.current = false;
  }
  function onPointerMove(e: React.PointerEvent) {
    if (dragFrom.current === null) return;
    if (Math.abs(e.clientX - dragFrom.current) > 8) dragged.current = true;
  }
  function onPointerUp(e: React.PointerEvent) {
    if (dragFrom.current === null) return;
    const delta = e.clientX - dragFrom.current;
    dragFrom.current = null;
    // The track itself is forced dir="ltr" (see below), so this is the ordinary LTR-carousel
    // reading: dragging left moves forward, exactly like the ChevronLeft "next" arrow below it.
    if (delta < -40) go(1);
    else if (delta > 40) go(-1);
  }

  return (
    <div className="flex flex-col gap-3 rounded-card bg-gradient-to-br from-warning-soft to-surface-1 p-4 shadow-sm">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-warning">
          <LifeBuoy size={18} aria-hidden />
          <span className="font-medium">
            {tickets.length === 1 ? 'تذكرة تحتاج ردك' : `${tickets.length} تذاكر تحتاج ردك`}
          </span>
        </div>
        {tickets.length > 1 ? (
          <span className="text-xs tabular-nums text-text-secondary">{at + 1} / {tickets.length}</span>
        ) : null}
      </div>

      <div className="relative overflow-hidden">
        {/* dir="ltr" HERE, DELIBERATELY — a flex row's axis order flips under the document's own
            RTL, which would make `translateX` math fight the reading direction (see this file's
            own header note). Forcing ltr on the TRACK ONLY keeps slide 0 first and translateX's
            sign simple; each slide gets dir="rtl" back below so its own Arabic text still reads
            right-to-left. */}
        <div dir="ltr"
             className="flex transition-transform duration-300 ease-out"
             style={{ transform: `translateX(${-at * 100}%)` }}
             onPointerDown={onPointerDown}
             onPointerMove={onPointerMove}
             onPointerUp={onPointerUp}
             onPointerCancel={() => { dragFrom.current = null; }}
        >
          {tickets.map((t) => (
            <button key={t.id ?? t.tenant} type="button" dir="rtl"
                   onClick={() => { if (!dragged.current) onOpen(t); }}
                   className="w-full shrink-0 cursor-grab select-none rounded-xl bg-surface-0 p-4 text-start shadow-sm active:cursor-grabbing"
                   style={{ touchAction: 'pan-y' }}>
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-medium text-text-secondary">{t.shop_name}</span>
                {t.status ? (
                  <span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${statusTone(t.status)}`}>
                    {t.status}
                  </span>
                ) : null}
              </div>
              <p className="mt-1.5 truncate font-medium">{t.subject || t.type || 'تذكرة بلا عنوان'}</p>
              {t.body ? <p className="mt-0.5 line-clamp-2 text-sm text-text-secondary">{t.body}</p> : null}
              {t.created_at ? (
                <span className="mt-2 block text-xs text-text-muted">{timeAgo(t.created_at)}</span>
              ) : null}
            </button>
          ))}
        </div>
      </div>

      {tickets.length > 1 ? (
        <div className="flex items-center justify-center gap-3">
          <button type="button" aria-label="التذكرة التالية" onClick={() => go(1)}
                 className="grid size-8 place-items-center rounded-full bg-surface-0 shadow-sm active:scale-95">
            <ChevronLeft size={16} aria-hidden />
          </button>
          <div className="flex items-center gap-1.5">
            {tickets.map((t, i) => (
              <span key={t.id ?? i}
                   className={`size-1.5 rounded-full transition-colors ${i === at ? 'bg-accent' : 'bg-surface-2'}`} />
            ))}
          </div>
          <button type="button" aria-label="التذكرة السابقة" onClick={() => go(-1)}
                 className="grid size-8 place-items-center rounded-full bg-surface-0 shadow-sm active:scale-95">
            <ChevronRight size={16} aria-hidden />
          </button>
        </div>
      ) : null}
    </div>
  );
}
