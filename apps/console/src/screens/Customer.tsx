/**
 * One customer, as his shop sees him.
 *
 * THE SCREEN «عملائي» COULD NOT OPEN. The list found him and stopped there: the owner tapped a row
 * and nothing happened, so the only question this section could answer was "does he exist". His
 * visits, his points and — the reason this file was written — WHICH OFFERS HE IS HOLDING were all
 * in the product and reachable from nowhere.
 *
 * THE OFFERS COME FIRST, and expired ones are shown here and nowhere else.
 *
 * The customer's own page and the field screen must never render a dead offer: it contradicts the
 * shop in front of the customer. The owner is asking a different question. "Did he get last
 * month's offer?" is as common as "what is he holding now", and an answer that hides everything
 * that ran out makes his own history unreadable — so they are here, dimmed and labelled, never
 * removed.
 *
 * AND THE JOIN IS THE PSEUDONYM. reminders holds no names at all — deliberately — so the offers
 * are fetched by the `subject_ref` that arrives with this one record and with no list.
 */
import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { Badge } from '@base-ui/design-system/Badge';
import { Button } from '@base-ui/design-system/Button';
import { EmptyState } from '@base-ui/design-system/EmptyState';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { action, call, type Catalog } from '../catalog';
import { partitionOffers, remaining, type Offer } from '../offers';
import type { Session } from '../session';

interface Record {
  customer: { id: string; phone: string; name?: string; subject_ref?: string; visits?: number };
  visits: { id: string; services?: string; occurred_at?: number }[];
}

/** A date an owner reads. Western digits, and the shop's own timezone rather than the browser's. */
function when(epoch: number): string {
  if (!epoch) return '';
  return new Date(epoch * 1000).toLocaleDateString('ar-SA-u-nu-latn', {
    timeZone: 'Asia/Riyadh', year: 'numeric', month: 'short', day: 'numeric',
  });
}

export function CustomerScreen({ session, catalog }: { session: Session; catalog: Catalog }) {
  const { id = '' } = useParams();
  const navigate = useNavigate();
  const [record, setRecord] = useState<Record | null | undefined>(undefined);
  const [offers, setOffers] = useState<Offer[] | null>(null);

  useEffect(() => {
    const a = action(catalog, 'operations.customer');
    if (!a || !id) { setRecord(null); return; }
    let stale = false;
    call<Record>(session, a, { id })
      .then((r) => {
        if (stale) return;
        setRecord(r);
        // THE SECOND CALL DEPENDS ON THE FIRST, and it cannot be avoided: the pseudonym is what
        // reminders knows him by, and only this record carries it.
        const o = action(catalog, 'reminders.customer_offers');
        const ref = r.customer?.subject_ref;
        if (!o || !ref) { setOffers([]); return; }
        call<{ offers: Offer[] }>(session, o, { subject_ref: ref, include_expired: true })
          .then((x) => { if (!stale) setOffers(x.offers ?? []); })
          // An offers read that fails must not empty the record: his visits are still true.
          .catch(() => { if (!stale) setOffers([]); });
      })
      .catch(() => { if (!stale) setRecord(null); });
    return () => { stale = true; };
  }, [id, session, catalog]);

  if (record === undefined) return <div className="p-4"><Skeleton height={240} /></div>;

  if (record === null) {
    return (
      <div className="p-4">
        <EmptyState
          title="تعذّر فتح سجل العميل"
          description="قد يكون العميل غير موجود، أو تعذّر الوصول إلى الخدمة. حاول بعد قليل."
        />
        <Button variant="ghost" onClick={() => navigate('/customers')}>رجوع إلى عملائي</Button>
      </div>
    );
  }

  const c = record.customer;
  // FROM THE TESTED MODULE, NOT FROM A COPY HERE. A rule that lives inside a component is a rule
  // only a rendered page can check — and the rendered page is the thing most likely to be rewritten.
  const [live, past] = partitionOffers(offers ?? []);

  return (
    <div className="flex flex-col gap-4 p-4">
      <header className="flex items-center justify-between gap-3">
        <span className="flex flex-col">
          <span className="text-lg font-semibold">{c.name || 'بلا اسم'}</span>
          <span dir="ltr" className="text-sm tabular-nums text-text-secondary">{c.phone}</span>
        </span>
        <Button variant="ghost" onClick={() => navigate('/customers')}>رجوع</Button>
      </header>

      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">عروضه</h2>
        {offers === null ? (
          <Skeleton height={90} />
        ) : offers.length === 0 ? (
          // NOT A FAULT, unlike an empty service catalogue. Nobody seeds a customer an offer — he
          // gets one when the shop runs one, and saying so plainly beats an apology.
          <p className="text-sm text-text-secondary">لم يصله أي عرض بعد.</p>
        ) : (
          <ul className="flex flex-col gap-3">
            {live.map((o) => (
              <li key={`${o.sent_at}-${o.text}`} className="rounded-xl bg-surface-2 p-3">
                <p className="font-medium">{o.text}</p>
                <p className="mt-1 text-sm text-text-secondary">
                  {o.services.length > 0 ? `على: ${o.services.join('، ')}` : 'على كل الخدمات'}
                </p>
                <p className="mt-2 flex items-center gap-2 text-sm">
                  <Badge tone="accent">ساري</Badge>
                  <span className="text-text-secondary">{remaining(o.expires_at)}</span>
                  <span className="text-text-secondary">· وصله {when(o.sent_at)}</span>
                </p>
              </li>
            ))}
            {/* DIMMED AND LABELLED, NEVER REMOVED. «هل وصله عرض الشهر الماضي؟» is a question the
                owner asks as often as «ماذا يحمل الآن؟», and an answer that hides what ran out
                makes his own history unreadable. */}
            {past.map((o) => (
              <li key={`${o.sent_at}-${o.text}`} className="rounded-xl bg-surface-2 p-3 opacity-60">
                <p className="font-medium">{o.text}</p>
                <p className="mt-2 flex items-center gap-2 text-sm">
                  <Badge tone="neutral">انتهى</Badge>
                  <span className="text-text-secondary">
                    {when(o.sent_at)} — {when(o.expires_at)}
                  </span>
                </p>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="rounded-card bg-surface-1 p-4 shadow-sm">
        <h2 className="mb-3 text-sm text-text-secondary">زياراته</h2>
        {record.visits.length === 0 ? (
          <p className="text-sm text-text-secondary">لا زيارات مسجّلة بعد.</p>
        ) : (
          <ul className="flex flex-col gap-2">
            {record.visits.slice(0, 20).map((v) => (
              <li key={v.id} className="flex items-center justify-between gap-3">
                <span>{v.services || 'زيارة'}</span>
                <span className="text-sm text-text-secondary">{when(v.occurred_at ?? 0)}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
