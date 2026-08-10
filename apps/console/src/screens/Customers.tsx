/**
 * «عملائي» — who I have, and who has not come back.
 *
 * THREE REASONS TO OPEN IT AND NO FOURTH: how many do I have, find this one, who is overdue.
 * Anything that does not serve one of those is analysis, and analysis is «محلّي».
 *
 * THE SEARCH IS THE FIRST THING BECAUSE IT IS THE FIRST REASON — and it is the one control on this
 * screen with a failure mode that costs a customer. Filtering the rows already on screen looks
 * identical in development and fails exactly as the spec warns: he types five correct digits, sees
 * nothing because that customer was not here today, and concludes the man is not registered.
 */
import { useEffect, useState } from 'react';
import { Search } from 'lucide-react';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { Badge } from '@base-ui/design-system/Badge';
import { action, call, type Catalog } from '../catalog';
import { suggestByPrefix, type CustomerHit } from '../api';
import type { Session } from '../session';

const MIN_PREFIX = 3;

export function CustomersScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const [query, setQuery] = useState('');
  const [matches, setMatches] = useState<CustomerHit[]>([]);
  const [recent, setRecent] = useState<CustomerHit[] | null>(null);

  useEffect(() => {
    const a = action(catalog, 'operations.recent');
    if (!a) { setRecent([]); return; }
    call<{ customers: CustomerHit[] }>(session, a, { limit: 50 })
      .then((x) => setRecent(x.customers))
      .catch(() => setRecent([]));
  }, [session, catalog]);

  /**
   * DEBOUNCED, AND GUARDED AGAINST ITS OWN HISTORY. This fires on every key of a ten-digit number
   * typed fast; without the `stale` flag the answer to three digits can land after the answer to
   * six and overwrite it, so the list would show matches for a prefix he has already moved past.
   */
  useEffect(() => {
    if (query.length < MIN_PREFIX) { setMatches([]); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      suggestByPrefix(session, query)
        .then((rows) => { if (!stale) setMatches(rows); })
        // A failed search must never block the screen: the list below still stands, and he can
        // still reach a customer through it.
        .catch(() => { if (!stale) setMatches([]); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [query, session]);

  const showing = query.length >= MIN_PREFIX ? matches : (recent ?? []);

  return (
    <div className="flex flex-col gap-4 p-4">
      <label className="relative block">
        <Search size={18} className="absolute top-1/2 -translate-y-1/2 start-3 text-text-muted" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="ابحث برقم الجوال أو الاسم"
          className="h-12 w-full rounded-xl bg-surface-1 ps-10 pe-4 shadow-sm placeholder:text-text-muted"
        />
      </label>

      {recent === null ? (
        <Skeleton height={200} />
      ) : showing.length === 0 ? (
        // TWO DIFFERENT EMPTIES, AND THEY MUST NOT SHARE A SENTENCE. "No customer matched" is a
        // search result; "you have no customers yet" is the state of the shop. Telling a new shop
        // that nothing matched suggests its data is missing rather than not yet created.
        query.length >= MIN_PREFIX ? (
          <EmptyState
            title="لا نتائج"
            description="تأكد من الرقم، أو سجّل زيارة جديدة لهذا العميل."
          />
        ) : (
          <EmptyState
            title="لا يوجد عملاء بعد"
            description="سجّل أول زيارة من «تسجيل زيارة» — العميل يُنشأ بزيارته."
          />
        )
      ) : (
        <ul className="flex flex-col gap-2">
          {showing.map((c) => (
            <li
              key={c.id}
              className="flex items-center justify-between rounded-card bg-surface-1 px-4 py-3 shadow-sm"
            >
              <div className="flex flex-col">
                <span dir="ltr" className="tabular-nums">{c.phone}</span>
                <span className="text-sm text-text-secondary">{c.name || 'بلا اسم'}</span>
              </div>
              {/* THE CONSENT STATE IS SHOWN BECAUSE IT CHANGES WHAT HE MAY DO, not as decoration:
                  a customer who withdrew still earns points and still gets service messages, and
                  the one thing that stops is marketing. An owner who cannot see it will assume an
                  offer reached everyone. */}
              {c.marketing === false ? (
                <Badge tone="neutral">أوقف التسويق</Badge>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
