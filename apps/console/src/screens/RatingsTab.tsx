/**
 * «التقييمات» — a tab inside «عملائي» (rating-app-feature.md phase 5), never a screen of its own:
 * a rating is a fact about a visit a customer already made, the same domain «عملائي» already
 * owns, not a new one.
 *
 * ABSENT ENTIRELY WHENEVER `operations.ratings` IS MISSING FROM THE CATALOGUE — same discipline as
 * every other action-gated card in this console: a shop that never bought the rating app (or one
 * where MSG_WORD_LIMIT-style kill switches never applied here, since this app has its own
 * `feature.rating` gate) simply never sees the tab, no dead control to explain.
 *
 * THE DEFAULT VIEW SURFACES THE UNHANDLED FIRST — an owner opening this tab wants to know who he
 * still owes a reply, not a chronological wall of five-star praise mixed in with it.
 */
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ChevronLeft, Star } from 'lucide-react';
import { EmptyState } from '../rj-ui/EmptyState';
import { Skeleton } from '../rj-ui/Skeleton';
import { Badge } from '../rj-ui/Badge';
import { Button } from '../rj-ui/Button';
import { action, call, type Catalog } from '../catalog';
import type { Session } from '../session';
import { scopeQuery } from '../branch-scope';

interface RatingRow {
  id: string; customer_id: string; rating: number; feedback_text: string; rated_at: number;
  rating_handled_at: number; rating_handled_note: string;
}

// WESTERN DIGITS, ALWAYS — check_deploy_wiring.py enforces 0-9 even inside Arabic text.
const STAR_OPTIONS = [
  { value: '', label: 'كل التقييمات' },
  { value: '5', label: '5 نجوم' },
  { value: '4', label: '4 نجوم' },
  { value: '3', label: '3 نجوم' },
  { value: '2', label: 'نجمتان' },
  { value: '1', label: 'نجمة واحدة' },
];

const HANDLED_OPTIONS = [
  { value: 'false', label: 'غير معالَجة' },
  { value: '', label: 'الكل' },
  { value: 'true', label: 'معالَجة' },
];

/** How long ago, in the words an owner uses — same convention as Customers.tsx's own `ago()`. */
function ago(at: number): string {
  const days = Math.floor((Date.now() / 1000 - at) / 86_400);
  if (days <= 0) return 'اليوم';
  if (days === 1) return 'أمس';
  if (days === 2) return 'قبل يومين';
  return `قبل ${days} أيام`;
}

export function RatingsTab(
  { session, catalog, branch }: { session: Session; catalog: Catalog; branch: string },
) {
  const navigate = useNavigate();
  const [stars, setStars] = useState('');
  const [handled, setHandled] = useState('false');
  const [rows, setRows] = useState<RatingRow[] | null | undefined>(undefined);
  const [noteDraft, setNoteDraft] = useState<Record<string, string>>({});
  const [busyId, setBusyId] = useState<string | null>(null);

  const listAction = action(catalog, 'operations.ratings');
  const handleAction = action(catalog, 'operations.mark_rating_handled');

  const load = () => {
    if (!listAction) { setRows(null); return; }
    const query: Record<string, string> = { ...scopeQuery(branch) };
    if (stars) query.stars = stars;
    if (handled) query.handled = handled;
    call<{ ratings: RatingRow[] }>(session, listAction, query)
      .then((x) => setRows(x.ratings ?? []))
      .catch(() => setRows(null));
  };

  useEffect(load, [session, catalog, branch, stars, handled]);   // eslint-disable-line react-hooks/exhaustive-deps

  if (!listAction) return null;

  const markHandled = async (id: string) => {
    if (!handleAction || busyId) return;
    setBusyId(id);
    try {
      await call(session, handleAction, { visit_id: id, note: noteDraft[id] ?? '' });
      // OPTIMISTIC REMOVAL FROM AN "unhandled" FILTER ONLY — on any other filter the row stays put
      // (its handled state genuinely changed, and re-fetching is the honest way to reflect that).
      if (handled === 'false') {
        setRows((cur) => (cur ?? []).filter((r) => r.id !== id));
      } else {
        load();
      }
    } catch {
      // A failed mark-handled leaves the row exactly as it was — no optimistic flip to undo.
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {/* PLAIN SINGLE-CHOICE PILLS, NOT `FilterMenu` — that component is a real multi-select
          (an array of chosen values), and both filters here are genuinely single-choice (one
          star rank, one handled state), so forcing them through a multi-select API would be the
          wrong shape wearing the right component. Same pill styling as PackagesTab.tsx's own
          recurrence picker. */}
      <div className="flex flex-wrap gap-1">
        {STAR_OPTIONS.map((o) => (
          <button key={o.value} type="button" onClick={() => setStars(o.value)}
                 className={
                   'rounded-full px-3 py-1 text-xs font-medium transition-colors ' +
                   (stars === o.value ? 'bg-accent text-accent-contrast'
                                     : 'bg-surface-2 text-text-secondary hover:bg-surface-3')
                 }>
            {o.label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1">
        {HANDLED_OPTIONS.map((o) => (
          <button key={o.value} type="button" onClick={() => setHandled(o.value)}
                 className={
                   'rounded-full px-3 py-1 text-xs font-medium transition-colors ' +
                   (handled === o.value ? 'bg-accent-soft text-accent-on-soft'
                                       : 'bg-surface-2 text-text-secondary hover:bg-surface-3')
                 }>
            {o.label}
          </button>
        ))}
      </div>

      {rows === undefined ? (
        <Skeleton height={200} />
      ) : rows === null ? (
        <EmptyState title="تعذّرت القراءة"
                   description="لم نستطع جلب التقييمات الآن — والخلل عندنا لا في محلك. أعد المحاولة بعد قليل." />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Star size={22} />}
          title={handled === 'false' ? 'لا تقييمات بانتظار المعالجة' : 'لا تقييمات بعد'}
          description={handled === 'false'
            ? 'كل تقييم وصل تمت معالجته — أو لم يصل تقييم جديد بعد.'
            : 'التقييمات تصل تلقائياً بعد الزيارة، عبر تطبيق التقييم.'}
        />
      ) : (
        <ul className="flex flex-col gap-2">
          {rows.map((r) => {
            const isHandled = r.rating_handled_at > 0;
            return (
              <li key={r.id}
                 className="flex flex-col gap-2 rounded-card bg-surface-1 p-4 shadow-sm">
                <div className="flex items-center justify-between gap-2">
                  <button type="button" onClick={() => navigate(`/customers/${r.customer_id}`)}
                         className="flex items-center gap-1 text-sm font-medium">
                    <span dir="ltr" className="flex items-center gap-0.5">
                      {Array.from({ length: 5 }, (_, i) => (
                        <Star key={i} size={14}
                             className={i < r.rating ? 'fill-warning text-warning' : 'text-text-muted'} />
                      ))}
                    </span>
                    <ChevronLeft size={14} className="text-text-muted" aria-hidden />
                  </button>
                  <span className="flex items-center gap-2">
                    {isHandled ? <Badge tone="neutral">معالَجة</Badge> : <Badge tone="warning">بانتظار المعالجة</Badge>}
                    <span className="text-xs text-text-muted">{ago(r.rated_at)}</span>
                  </span>
                </div>
                {r.feedback_text ? (
                  <p className="text-sm text-text-secondary">{r.feedback_text}</p>
                ) : null}
                {isHandled ? (
                  r.rating_handled_note ? (
                    <p className="text-xs text-text-muted">ملاحظتك: {r.rating_handled_note}</p>
                  ) : null
                ) : handleAction ? (
                  <div className="flex items-center gap-2">
                    <input
                      value={noteDraft[r.id] ?? ''}
                      onChange={(e) => setNoteDraft((m) => ({ ...m, [r.id]: e.target.value }))}
                      placeholder="ملاحظة (اختياري) — مثال: تواصلنا معه واعتذرنا"
                      maxLength={500}
                      className="h-9 flex-1 rounded-lg bg-surface-2 px-2 text-sm"
                    />
                    <Button variant="outline" size="sm" disabled={busyId === r.id}
                           onClick={() => markHandled(r.id)}>
                      تمت المعالجة
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
