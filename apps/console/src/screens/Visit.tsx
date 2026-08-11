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
  applyOffer, balanceFor, customerByPhone, fetchCatalogue, offerFor, recentCustomers, redeem,
  suggestByPrefix,
  type Balance, type CatalogueService, type CustomerHit, type FieldOffer, type SectorField,
} from '../api';
import { Keypad } from '../Keypad';
import { ServiceGrid } from '../ServiceGrid';
import { Steps } from '../Steps';
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
  /**
   * WHAT HE HAS, AND WHAT HE CAN SPEND IT ON — beside the offer, from the same lookup.
   *
   * ONE by-phone CALL FOR BOTH. The offer and the balance are both keyed by the pseudonym, and
   * two lookups for one number would double a request that sits inside a five-second journey.
   */
  const [subject, setSubject] = useState('');
  const [balance, setBalance] = useState<Balance | null>(null);
  const [redeeming, setRedeeming] = useState('');
  /**
   * WHETHER THE OPERATOR SAID THE CUSTOMER TOOK HIS OFFER.
   *
   * Held on the screen until the visit is saved, because the offer is applied TO a visit and the
   * visit does not exist until he presses save. Consuming it earlier would spend an entitlement
   * against something that may never be recorded.
   */
  const [applying, setApplying] = useState(false);
  const [redeemed, setRedeemed] = useState<string | null>(null);

  /**
   * WHAT WE KNOW ABOUT HIS ENTITLEMENTS, and «we have not asked yet» is not «he has none».
   *
   * The offers step is REMOVED from the journey when there is nothing in it — an empty page with
   * a progress dot that never lights is worse than no page. But four states have to stay apart or
   * the step flickers into and out of existence under a moving thumb:
   *
   *   idle    — no customer identified yet. No step, and nothing to say about it.
   *   asking  — the answer is in flight. The step STAYS, because removing it now and restoring it
   *             half a second later moves the ground under him mid-swipe.
   *   known   — we asked and were answered. Present only if there is something to spend.
   *   failed  — we asked and could not hear. NEVER reported as "no offers": silence is not
   *             absence, and telling a customer he holds nothing when he holds something is the
   *             one wrong answer he will argue about at the counter.
   */
  const [perks, setPerks] = useState<'idle' | 'asking' | 'known' | 'failed'>('idle');

  useEffect(() => {
    if (phone.length < 9) {
      setOffer(null); setBalance(null); setSubject(''); setRedeemed(null); setPerks('idle');
      return;
    }
    setPerks('asking');
    let stale = false;
    const id = window.setTimeout(() => {
      customerByPhone(session, phone)
        .then(async (r) => {
          const ref = r.customer?.subject_ref ?? '';
          if (stale) return;
          setSubject(ref);
          // A NUMBER WE HAVE NEVER SEEN. He is new — not empty-handed, and the two are different
          // sentences on the next page.
          if (!ref) { setOffer(null); setBalance(null); setPerks('known'); return; }
          // SETTLED, NOT ALL: one failing must not blank the other. A shop without the loyalty
          // feature has no balance to read, and that is not a reason to hide his offer.
          const [o, b] = await Promise.allSettled([offerFor(session, ref), balanceFor(session, ref)]);
          if (stale) return;
          setOffer(o.status === 'fulfilled' ? o.value : null);
          setBalance(b.status === 'fulfilled' ? b.value : null);
          // BOTH FAILING is the only case we cannot see through. One failing is ordinary — a shop
          // without the loyalty feature has no balance, and that says nothing about his offer.
          setPerks(o.status === 'rejected' && b.status === 'rejected' ? 'failed' : 'known');
        })
        .catch(() => { if (!stale) { setOffer(null); setBalance(null); setPerks('failed'); } });
    }, 220);
    return () => { stale = true; window.clearTimeout(id); };
  }, [phone, session]);

  /**
   * Spend them, in front of him.
   *
   * THE BALANCE IS RE-READ FROM THE SERVER rather than subtracted here. The screen's arithmetic
   * and the ledger's would agree today and diverge the first time a rule changes, and the number
   * the customer is told at the counter must be the one the shop is actually holding.
   */
  const spend = useCallback(async (rewardId: string, rewardName: string) => {
    if (!subject || redeeming) return;
    setRedeeming(rewardId);
    try {
      await redeem(session, subject, rewardId);
      setRedeemed(rewardName);
      setBalance(await balanceFor(session, subject));
      window.setTimeout(() => setRedeemed(null), 4000);
    } catch (e) {
      // THE SENTENCE THE SERVICE WROTE. A refusal here is a rule — not enough points, a reward
      // that needs a manager — and the operator is standing in front of the customer.
      setNote(e instanceof Error ? e.message : 'تعذّر الاستبدال.');
      window.setTimeout(() => setNote(null), 4000);
    } finally {
      setRedeeming('');
    }
  }, [redeeming, session, subject]);

  const ready = chosen.length > 0 && phone.length >= 9;

  const save = useCallback(() => {
    if (!ready) return;
    // MINTED HERE, AT THE PRESS. Not inside the queue and not inside the request — a key created
    // where the request is sent would be a new key on every retry, which is exactly no key.
    const key = newIdempotencyKey();
    queue.add({
      phone,
      service_ids: chosen,
      name: name.trim() || undefined,
      plate: showPlate && plate.trim() ? plate.trim() : undefined,
      meter: showMeter && meter ? Number(meter) : undefined,
      idempotency_key: key,
    }, session);

    // THE OFFER IS SPENT AGAINST THIS VISIT, and the visit's own key identifies it — the one
    // value that is the same on every retry, which is exactly what "one offer per visit" needs.
    //
    // FIRE AND FORGET, DELIBERATELY. The visit is already queued and will reach the server on its
    // own schedule; making the operator wait for a second round trip would spend the five-second
    // budget on something the customer is not watching. A failure here loses the application, not
    // the visit — and the offer is still live, so it can be applied again.
    if (applying && subject) {
      applyOffer(session, subject, key).catch(() => undefined);
    }
    setApplying(false);

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
  }, [applying, chosen, meter, name, phone, plate, ready, session, showMeter, showPlate, subject]);

  if (!isSignedIn(session)) {
    // SAYS SO PLAINLY RATHER THAN INVENTING A TENANT. A placeholder establishment would let every
    // screen appear to work while writing visits into data nobody owns.
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6 text-center">
        <p className="text-lg text-text-secondary">لم تُفتح الجلسة بعد.</p>
      </main>
    );
  }


  // ── THE THREE PANES OF ONE VISIT ──────────────────────────────────────────────────────────
  // Named here rather than inlined below, because they are about to become three SCREENS the
  // operator swipes between rather than three regions he scrolls past. Extracting them first,
  // with no change in what they render, keeps that move reviewable: this commit is a rename.
  const identityPane = (
            /* THE PANE IS THE SCREEN, so it is a column that fills it: display, then the matches
               in a space of their own, then the keypad taking what is left. The matches used to
               live on the LAST page — the operator typed a number here and the customer he was
               looking for appeared two swipes away. */
            <div className="flex h-full flex-col gap-2">
              <div
                dir="ltr"
                className="grid h-[clamp(3rem,7dvh,3.5rem)] items-center rounded-xl bg-surface-1 px-4 text-end text-3xl font-semibold tabular-nums shadow-sm"
              >
                {phone || <span className="text-text-secondary">05…</span>}
              </div>
              {/* THE KEYPAD IS FOR A THUMB, NOT FOR A DESK. On a machine with a real keyboard it
                  was a second, larger way to type ten digits — and it pushed everything that
                  matters below the fold. `.touch-only` is a pointer test, not a width test: see
                  index.css for why the width variant could not even compile here. */}
              {/* THE MATCHES, WHERE HE IS TYPING — and in a fixed slot. A list that grows pushes
                the keypad down under his thumb between one digit and the next, so the key he
                aims at is not the key he hits. The height is reserved whether or not anyone
                matches; an empty two-line gap costs nothing and a moving keypad costs a wrong
                number saved against the wrong customer. */}
            <div className="min-h-0 flex-1 overflow-y-auto">
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
            </div>

            <div className="touch-only">
                <Keypad value={phone} onChange={setPhone} />
              </div>
            </div>

  );

  const perksPane = (
    <>
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
                {/* THE TAP, AND IT IS NOT PRESSED FOR HIM. A customer may be holding this for next
                    month; applying it because he happened to walk in would be taking something from
                    him. So it is a deliberate act, and it says what it will do. */}
                <label className="mt-2 flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={applying}
                    onChange={(e) => setApplying(e.target.checked)}
                    className="h-5 w-5"
                  />
                  <span>طبّقتُ العرض على هذه الزيارة</span>
                </label>
              </div>
            ) : null}

            {/* HIS POINTS, AND THE ONE TAP THAT SPENDS THEM.
                Under the offer, because an offer is already his and points are a choice he makes.
                Nothing renders without a balance: a shop with no loyalty programme must not be
                shown an empty points box on the screen it uses a hundred times a day. */}
            {balance ? (
              <div className="rounded-xl bg-surface-1 p-3 shadow-sm">
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-sm text-text-secondary">رصيده</span>
                  <span className="tabular-nums text-xl font-semibold">{balance.points} نقطة</span>
                </div>

                {redeemed ? (
                  <p className="mt-2 rounded-lg bg-accent-soft p-2 text-accent-on-soft">
                    تم استبدال «{redeemed}» — أخبره برصيده الجديد.
                  </p>
                ) : null}

                {balance.rewards.length > 0 ? (
                  <ul className="mt-2 flex flex-col gap-2">
                    {/* ONLY WHAT HE CAN AFFORD — the service filtered before answering. A sheet
                        listing everything and grey­ing out most of it turns a moment of goodwill
                        into a list of things he cannot have. */}
                    {balance.rewards.map((r) => (
                      <li key={r.id}>
                        <button
                          type="button"
                          disabled={Boolean(redeeming)}
                          onClick={() => spend(r.id, r.name)}
                          className="flex w-full items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-3 text-start disabled:opacity-60"
                        >
                          <span>{r.name}</span>
                          <span className="shrink-0 tabular-nums text-sm text-text-secondary">
                            {r.cost} نقطة · ويبقى له {balance.points - r.cost}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                ) : balance.to_next_reward > 0 ? (
                  // ENCOURAGEMENT, NOT AN APOLOGY — and only when there is something true to say.
                  // Zero means either he can afford everything or the shop has no rewards, and
                  // «تبقى لك 0 نقطة» is a sentence that means nothing to the person reading it.
                  <p className="mt-1 text-sm text-text-secondary">
                    تبقّى له {balance.to_next_reward} نقطة لأقرب مكافأة.
                  </p>
                ) : null}
              </div>
            ) : null}
    </>
  );

  // ── the plate, alone, and first ───────────────────────────────────────────────────────────
  // In بنشر, مغسلة and تنجيد the customer IS the car: it rolls in, the operator reads the plate
  // off the bumper, and everything else — including whose phone this is — comes after. It used to
  // sit third in a column of optional fields, below the number of a person who may not be the
  // person driving.
  const platePane = (
    <div className="flex h-full flex-col justify-center gap-3">
      <input
        value={plate}
        onChange={(e) => setPlate(e.target.value)}
        placeholder="رقم اللوحة"
        autoFocus
        className="h-16 rounded-2xl bg-surface-1 px-4 text-center text-2xl font-semibold shadow-sm placeholder:text-lg placeholder:font-normal placeholder:text-text-secondary"
      />
      <p className="text-center text-sm text-text-secondary">
        اكتب حرفين أو رقمين وتظهر لك السيارة إن كانت عندنا.
      </p>
    </div>
  );

  /** Is there anything on the entitlements page worth turning to? */
  const hasPerks = Boolean(offer?.text) || Boolean(balance?.rewards?.length);

  const detailsPane = (
    <>
      {/* WHAT HE TOOK — the last page, and the one he spends the most time on. */}
      {/* AND ONE TAP TO UNDO ALL OF IT. A customer changes his mind and walks out with the car
          half-quoted; without this the operator un-taps six tiles one by one while the next car
          waits. It only appears when there is something to clear — a button that does nothing is
          a button he has to think about every time he passes it. */}
      {chosen.length > 0 ? (
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-sm text-text-secondary tabular-nums">
            المختار: {chosen.length}
          </span>
          <button
            type="button"
            onClick={() => setChosen([])}
            className="min-h-[44px] rounded-xl bg-surface-2 px-4 text-sm font-semibold"
          >
            مسح المختارة
          </button>
        </div>
      ) : null}
      <ServiceGrid services={services} selected={chosen} onToggle={toggle} />

      {/* WHY HE NEVER SAW AN OFFERS PAGE. Skipping a step silently makes an operator wonder what
          he missed — and «لا عروض» is the wrong answer for a customer we have never met, and a
          lie when we simply could not ask. Three facts, three sentences. */}
      {!hasPerks && phone.length >= 9 ? (
        <p className="mb-2 rounded-xl bg-surface-2 px-3 py-2 text-sm text-text-secondary">
          {perks === 'failed'
            ? 'تعذّر التحقق من عروضه ونقاطه الآن — سجّل الزيارة، ولا شيء يضيع.'
            : subject
              ? 'لا عروض ولا نقاط مستحقّة لهذا العميل.'
              : 'عميل جديد — أول زيارة له عندك.'}
        </p>
      ) : null}
            <div className="flex flex-col gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="الاسم (اختياري)"
                className="h-14 rounded-xl bg-surface-1 px-4 text-lg shadow-sm placeholder:text-text-secondary"
              />

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
    </>
  );

  return (
    // NO PADDING AND NO BOTTOM GAP. The journey measures the room it has and fills it exactly;
    // anything this wrapper adds is height the panes cannot see and the arrows pay for.
    <main className="bg-surface-0 text-text-primary">
      <div className="mx-auto max-w-4xl">
        {/* NO "TODAY'S CUSTOMERS" STRIP HERE, AND IT WAS THE FIRST THING ON THE SCREEN.
            The premise was that the same car returns an hour later. It does not: the customer
            drives away and comes back in weeks. So the strip spent its height — the height the
            journey needs — on a shortcut nobody reaches for, on the screen that can least afford
            it. Recent customers live in «عملائي», where looking someone up is the point. */}

        {/* ── THE JOURNEY ───────────────────────────────────────────────────────────────────
            One question per screen, moved by a thumb. In a vehicle sector the plate comes first
            and alone: the car rolls in and that is what is read off it. Everywhere else the
            person IS the phone number, so that is the first screen instead.

            THE ENTITLEMENTS STEP IS ABSENT WHEN THERE IS NOTHING IN IT, and the step after says
            which kind of nothing it was — a new customer is not a customer with no offers, and
            neither is a lookup we could not complete. */}
        <Steps
          steps={[
            ...(showPlate
              ? [{ id: 'plate', title: 'رقم اللوحة', body: platePane }]
              : []),
            { id: 'who', title: showPlate ? 'رقم جوال صاحب السيارة' : 'رقم جوال العميل',
              body: identityPane },
            { id: 'perks', title: 'عروضه ونقاطه',
              // ASKING KEEPS THE STEP. Removing it the instant a request goes out and restoring it
              // when the answer lands moves the ground under a thumb already in motion.
              when: perks === 'asking' || hasPerks,
              body: perksPane },
            { id: 'what', title: 'الخدمات', body: detailsPane },
          ]}
          // THE SAVE BAR LIVES INSIDE THE JOURNEY, and it used to sit after it. That is what pushed
          // the arrows below the fold: the pane sized itself to the window while a second bar was
          // still stacked underneath, so the one control the whole screen exists for was reachable
          // only by scrolling — on a screen built expressly not to scroll.
          done={(
    <div className="flex items-center gap-3">
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
            className="h-11 flex-1 rounded-xl bg-accent text-base font-bold text-white transition-transform active:scale-[0.98] disabled:opacity-40"
          >
            حفظ وإرسال
          </button>
    </div>
          )}
        />

      </div>

      {/* THE SAVE BAR IS FIXED TO THE BOTTOM. It is the only button that must be reachable without
          looking, and a button that scrolls is a button that is somewhere else each time. */}
      {/* STICKY INSIDE THE CONTENT, NOT FIXED TO THE VIEWPORT.
          `fixed inset-x-0` spans the whole window, so on a desktop the bar ran underneath the
          sidebar — the shell's own column, which it has no business covering. Sticky keeps it
          pinned to the bottom of the scrolling area it belongs to, and it can never reach past
          the column it lives in, at any width and with the sidebar collapsed or open. */}
    </main>
  );
}

