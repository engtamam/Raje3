/**
 * ONE SCREEN. The whole visit, in three stacked parts, with no navigation anywhere (spec 4.3).
 *
 * The order is services → customer → save, and it is the order of the work rather than the order
 * of the data (spec 4.5). The technician finishes the job with the services in front of him and
 * taps them; only then does he turn to the customer. A screen that asked for the phone number
 * first would be asking him to stop working in order to feed the system.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  customerByPhone, fetchCatalogue, offerFor, recentCustomers, suggestByPrefix,
  type CatalogueService, type CustomerHit, type FieldOffer, type SectorField,
} from '../api';
import { Keypad } from '../Keypad';
import { ServiceGrid } from '../ServiceGrid';
import { newIdempotencyKey, queue, type Queued } from '../queue';
import { isSignedIn, useSession } from '../session';

/** How few digits are worth a search. Below this every establishment matches and the list is
 *  noise; this is the shortest prefix that narrows anything in a Saudi number. */
const MIN_PREFIX = 3;

export function Visit() {
  const { session } = useSession();
  const [services, setServices] = useState<CatalogueService[]>([]);
  const [fields, setFields] = useState<SectorField[]>([]);
  const [recent, setRecent] = useState<CustomerHit[]>([]);
  const [chosen, setChosen] = useState<string[]>([]);
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [plate, setPlate] = useState('');
  const [meter, setMeter] = useState('');
  const [note, setNote] = useState<string | null>(null);
  // EVERY ROW THE QUEUE HOLDS — waiting AND stuck. `subscribe` emits the whole list, so counting
  // it as "waiting to be sent" counted visits that will never be sent among them, and the number
  // an operator watched go down would have stalled at one for ever with no explanation.
  const [queued, setQueued] = useState<Queued[]>([]);
  const pending = queued.filter((r) => !r.stuck);
  const stuck = queued.filter((r) => r.stuck);
  const [matches, setMatches] = useState<CustomerHit[]>([]);

  // THE SERVER SAID SO. Not a list of sector keys in this file — that would be our own data
  // living where our console cannot change it (spec 13.2).
  const has = (n: string) => fields.some((f) => f.name === n);
  const showPlate = has('plate');
  const showMeter = has('meter');

  useEffect(() => {
    if (!isSignedIn(session)) return;
    fetchCatalogue(session)
      .then((r) => { setServices(r.services); setFields(r.fields ?? []); })
      .catch(() => { setServices([]); setFields([]); });
    recentCustomers(session).then((r) => setRecent(r.customers)).catch(() => setRecent([]));
  }, [session]);

  // THE QUEUE DRAINS ON EVERY SIGNAL THE BROWSER GIVES US, not on a timer. `online` is the one
  // that matters in a workshop — the tablet knows it reconnected long before a poll would.
  useEffect(() => {
    const off = queue.subscribe(setQueued);
    const go = () => void queue.drain(session);
    window.addEventListener('online', go);
    window.addEventListener('focus', go);
    go();
    return () => {
      off();
      window.removeEventListener('online', go);
      window.removeEventListener('focus', go);
    };
  }, [session]);

  const toggle = useCallback((id: string) => {
    setChosen((cur) => (cur.includes(id) ? cur.filter((x) => x !== id) : [...cur, id]));
  }, []);

  /**
   * THE MATCHES, FROM SEARCH-SERVICE — not from a filter over `recent`.
   *
   * Filtering the ten customers already on screen would have looked identical in development and
   * failed in exactly the way the spec warns about: the operator types five correct digits, sees
   * nothing because the customer was not here today, and registers him a second time.
   *
   * DEBOUNCED, because this fires on every key of a ten-digit number typed fast, and because the
   * request that started three digits ago must not overwrite the answer to the current one — the
   * `stale` flag is what keeps an old response from replacing a newer one.
   */
  useEffect(() => {
    if (phone.length < MIN_PREFIX) { setMatches([]); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      suggestByPrefix(session, phone)
        .then((rows) => { if (!stale) setMatches(rows); })
        // A search that fails must never block the entry. He can still type the whole number and
        // save; a missing suggestion costs a second, a blocked screen costs the visit.
        .catch(() => { if (!stale) setMatches([]); });
    }, 180);
    return () => { stale = true; window.clearTimeout(id); };
  }, [phone, session]);

  /**
   * HIS OFFER, AT THE COUNTER — the one place it can be honoured.
   *
   * ONLY ON A COMPLETE NUMBER. A prefix identifies several people, and showing one man's
   * entitlement while another's number is half-typed is worse than showing none: the worker reads
   * it aloud, and the customer in front of him was never sent it.
   *
   * AND IT NEVER BLOCKS THE ENTRY. A failed lookup leaves the offer unshown and the visit
   * recordable — this screen is used a hundred times a day and its budget is five seconds.
   */
  const [offer, setOffer] = useState<FieldOffer | null>(null);
  useEffect(() => {
    if (phone.length < 9) { setOffer(null); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      customerByPhone(session, phone)
        .then((r) => (r.customer?.subject_ref ? offerFor(session, r.customer.subject_ref) : null))
        .then((o) => { if (!stale) setOffer(o); })
        .catch(() => { if (!stale) setOffer(null); });
    }, 220);
    return () => { stale = true; window.clearTimeout(id); };
  }, [phone, session]);

  const ready = chosen.length > 0 && phone.length >= 9;

  const save = useCallback(() => {
    if (!ready) return;
    queue.add({
      phone,
      service_ids: chosen,
      name: name.trim() || undefined,
      plate: showPlate && plate.trim() ? plate.trim() : undefined,
      meter: showMeter && meter ? Number(meter) : undefined,
      // MINTED HERE, AT THE PRESS. Not inside the queue and not inside the request — a key created
      // where the request is sent would be a new key on every retry, which is exactly no key.
      idempotency_key: newIdempotencyKey(),
    }, session);

    // CLEARED ON THE QUEUE, NOT ON THE SERVER. The next customer is already waiting; a screen that
    // held still for a round trip would spend its five-second budget on a network the operator
    // cannot see and cannot fix.
    setChosen([]);
    setPhone('');
    setName('');
    setPlate('');
    setMeter('');
    setNote('تم الحفظ ✓');
    window.setTimeout(() => setNote(null), 1500);
  }, [chosen, meter, name, phone, plate, ready, session, showMeter, showPlate]);

  if (!isSignedIn(session)) {
    // SAYS SO PLAINLY RATHER THAN INVENTING A TENANT. A placeholder establishment would let every
    // screen appear to work while writing visits into data nobody owns.
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6 text-center">
        <p className="text-lg text-text-secondary">لم تُفتح الجلسة بعد.</p>
      </main>
    );
  }

  return (
    <main className="min-h-dvh bg-surface-0 p-3 text-text-primary">
      <div className="mx-auto flex max-w-4xl flex-col gap-3 pb-24">
        <ServiceGrid services={services} selected={chosen} onToggle={toggle} />

        {/* TODAY'S CUSTOMERS, ONE TAP (spec 4.3). The same car comes back an hour later because a
            second thing was found wrong with it, and making the operator retype ten digits for a
            customer he served this morning is the friction this whole screen exists to remove. */}
        {recent.length > 0 ? (
          <div className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
            {recent.map((c) => (
              <button
                key={c.id}
                type="button"
                onClick={() => { setPhone(c.phone); setName(c.name ?? ''); }}
                className="shrink-0 rounded-xl bg-surface-1 px-3 py-2 text-sm shadow-sm active:scale-95"
              >
                <span dir="ltr" className="tabular-nums">{c.phone.slice(-4)}</span>
                {c.name ? <span className="ms-2 text-text-secondary">{c.name}</span> : null}
              </button>
            ))}
          </div>
        ) : null}

        <section className="grid gap-3 sm:grid-cols-2">
          <div className="flex flex-col gap-2">
            <div
              dir="ltr"
              className="h-14 rounded-xl bg-surface-1 px-4 text-end text-3xl font-semibold tabular-nums leading-[3.5rem] shadow-sm"
            >
              {phone || <span className="text-text-secondary">05…</span>}
            </div>
            <Keypad value={phone} onChange={setPhone} />
          </div>

          {/* HIS OFFER, WHERE THE WORK HAPPENS. Directly under the number, above the matches:
              by the time it appears the number is complete, so there is exactly one person it can
              belong to. Loud on purpose — this is the sentence the customer is about to ask about,
              and a worker who misses it has taken money for something already paid for. */}
          {offer?.text ? (
            <div className="rounded-xl bg-accent-soft p-3 text-accent-on-soft shadow-sm">
              <div className="mb-1 text-sm font-semibold">عرضٌ خاص بهذا العميل</div>
              <div>{offer.text}</div>
              {offer.expires_at ? (
                <div className="mt-1 text-sm tabular-nums opacity-80">
                  ينتهي {new Date(offer.expires_at * 1000).toLocaleDateString('ar-SA-u-ca-gregory')}
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="flex flex-col gap-2">
            {/* THE MATCHES APPEAR WHILE HE TYPES. Spec 4.3: whoever types five correct digits and
                sees nothing concludes the customer is new — and registers him a second time. */}
            {matches.length > 0 ? (
              <div className="flex flex-col gap-1">
                {matches.slice(0, 4).map((c) => (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => { setPhone(c.phone); setName(c.name ?? ''); }}
                    className="flex items-center justify-between rounded-xl bg-surface-1 px-3 py-2 text-start shadow-sm active:scale-95"
                  >
                    <span dir="ltr" className="tabular-nums">{c.phone}</span>
                    <span className="text-text-secondary">{c.name || '—'}</span>
                  </button>
                ))}
              </div>
            ) : null}

            {/* PRESENT FROM THE FIRST VISIT, REQUIRED AT NONE (spec 4.3). No asterisk and no
                validation: he cannot ask a stranger his name while taking his key, but after five
                visits he knows it and writes it in a quiet moment. */}
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="الاسم (اختياري)"
              className="h-14 rounded-xl bg-surface-1 px-4 text-lg shadow-sm placeholder:text-text-secondary"
            />

            {showPlate ? (
              <input
                value={plate}
                onChange={(e) => setPlate(e.target.value)}
                placeholder="رقم اللوحة"
                className="h-14 rounded-xl bg-surface-1 px-4 text-lg shadow-sm placeholder:text-text-secondary"
              />
            ) : null}

            {showMeter ? (
              <input
                value={meter}
                onChange={(e) => setMeter(e.target.value.replace(/\D/g, ''))}
                inputMode="numeric"
                placeholder="قراءة العدّاد"
                dir="ltr"
                className="h-14 rounded-xl bg-surface-1 px-4 text-lg tabular-nums shadow-sm placeholder:text-text-secondary"
              />
            ) : null}
          </div>
        </section>
      </div>

      {/* THE SAVE BAR IS FIXED TO THE BOTTOM. It is the only button that must be reachable without
          looking, and a button that scrolls is a button that is somewhere else each time. */}
      {/* STICKY INSIDE THE CONTENT, NOT FIXED TO THE VIEWPORT.
          `fixed inset-x-0` spans the whole window, so on a desktop the bar ran underneath the
          sidebar — the shell's own column, which it has no business covering. Sticky keeps it
          pinned to the bottom of the scrolling area it belongs to, and it can never reach past
          the column it lives in, at any width and with the sidebar collapsed or open. */}
      <div className="sticky bottom-0 -mx-4 border-t border-border bg-surface-0/95 p-3 backdrop-blur">
        <div className="mx-auto flex max-w-4xl items-center gap-3">
          {pending.length > 0 ? (
            <span className="shrink-0 text-sm text-text-secondary tabular-nums">
              بانتظار الإرسال: {pending.length}
            </span>
          ) : null}
          {/* AND THE ONES THAT WILL NEVER GO. The queue has always told these apart — a 400, a 403
              or a 404 is not a network to wait out, and retrying it for ever burns battery and
              hides the problem — but it told nobody: the visit left the screen, the counter said
              nothing, and a shop lost a customer with no reminder, no points and no metric, in
              silence. That silence was the whole reason for holding it rather than dropping it. */}
          {stuck.length > 0 ? (
            <span className="shrink-0 text-sm text-danger tabular-nums">
              لم تُرسَل: {stuck.length} — تواصل معنا
            </span>
          ) : null}
          {note ? <span className="shrink-0 text-sm text-accent">{note}</span> : null}
          <button
            type="button"
            onClick={save}
            disabled={!ready}
            className="h-16 flex-1 rounded-2xl bg-accent text-xl font-bold text-white shadow-lg transition-transform active:scale-[0.98] disabled:opacity-40"
          >
            حفظ وإرسال
          </button>
        </div>
      </div>
    </main>
  );
}

