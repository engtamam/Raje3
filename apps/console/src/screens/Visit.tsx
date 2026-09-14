/**
 * ONE SCREEN. The whole visit, in three stacked parts, with no navigation anywhere (spec 4.3).
 *
 * THE ORDER IS THE CUSTOMER FIRST: plate → who → what he carries → services → save (spec 4.3).
 *
 * This comment used to say the opposite, and cited a section that has since been corrected: the
 * order was services-first, because that is the order of the WORK rather than of the data. The
 * argument is true and it is not enough. An offer and a points balance cannot be shown before we
 * know who the customer is — so services-first surfaces the offer AFTER the technician has already
 * chosen what he is doing, which is after the moment the offer was sent for.
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { CheckCircle2, Gift, Pencil } from 'lucide-react';
import {
  balanceFor, customerByPhone, customerByPlate, earnSettings, fetchCatalogue,
  offerFor, pointsByService, type CataloguePackage, type EarnSettings,
  redeem,
  suggestByPrefix,
  type Balance, type CatalogueService, type CustomerHit, type FieldOffer, type VisitField,
  sentenceFor,
} from '../api';
import { asLocal } from '../phone';
import { Button } from '../rj-ui/Button';
import { ServiceGrid } from '../ServiceGrid';
import { Steps } from '../Steps';
import { newIdempotencyKey, queue, type Queued } from '../queue';
import { proof } from '../operator';
import { WhoIsSaving } from '../WhoIsSaving';
import { isSignedIn, useSession } from '../session';
import { digitsOnly, western } from '../digits';
import { TodayBookingsStrip } from '../TodayBookingsStrip';
import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { useOperatorI18n, tf } from '../operator-i18n';
import { AssistantHint } from '../AssistantHint';
import './visit-i18n';

/**
 * One box, and the separator appears inside it.
 *
 * TWO BOXES WERE TOO BIG FOR A PHONE — side by side they took a third of the screen and left the
 * hint wrapping under them. And the split was ours, not the plate's: a Saudi plate is one thing
 * written in two parts, so it is one field that knows its own shape.
 *
 * FOUR DIGITS THEN THREE LETTERS is the Saudi maximum, and fewer of either is ordinary — a
 * two-digit plate is a real plate, so nothing here waits for a length before accepting input.
 * Anything else is dropped rather than refused: a workshop tablet's keyboard produces stray
 * characters, and a box that rejects a whole entry over one of them is a box he fights.
 *
 * LATIN AND UPPERCASED, because both scripts are on the metal and letting each operator choose
 * makes «ABC 1234» and «ا ب ج 1234» two customers with one car.
 *
 * The space is INSERTED, never typed. He types 1234ABC and reads 1234 ABC, which is also exactly
 * what gets stored and indexed — see seams.py.
 */

export function formatPlate(raw: string): string {
  // FOLD BEFORE STRIPPING. This line used to delete Arabic-Indic digits along with the
  // punctuation, so `formatPlate('ا ب ج ٤٥٦')` returned '' and the
  // `plateOk` guard below — written expressly to accept those digits — could never see one.
  const folded = western(raw);
  const digits = digitsOnly(folded).slice(0, 4);
  // A LETTER IN ANY SCRIPT, BECAUSE BOTH ARE STAMPED ON THE PLATE. This used to keep `a-zA-Z` and
  // nothing else, so an Arabic-lettered plate came back with no letters at all — and `plateOk`
  // below, which requires one, then held the save button DISABLED. The operator typed what was on
  // the car and the screen simply would not let him continue, with no message, because a disabled
  // button has nothing to say. Meanwhile `operations/core/plate.py` accepted that same plate
  // happily: the screen was stricter than the service it feeds, which is the one direction that
  // costs a visit. `fixtures/plates.json` now holds the cases and both sides assert against it.
  //
  // `toUpperCase` stays for the Latin half and is a no-op on Arabic.
  const letters = Array.from(folded).filter((ch) => /\p{L}/u.test(ch)).join('')
    .toUpperCase().slice(0, 3);
  return letters ? `${digits} ${letters}`.trim() : digits;
}

/** How few digits are worth a search. Below this every establishment matches and the list is
 *  noise; this is the shortest prefix that narrows anything in a Saudi number. */
const MIN_PREFIX = 3;

export function Visit() {
  const { session } = useSession();
  const { t } = useOperatorI18n();
  // ONE BRANCH ONLY, THE SAME RULE THE GRID ITSELF FOLLOWS — today's bookings strip needs a
  // single branch to ask about; a single-branch shop resolves it silently, a multi-branch one
  // not yet narrowed simply shows no strip rather than guessing which branch's bookings to show.
  const outlet = useOutletContext<ShellContext | undefined>();
  const branchScopeId = outlet?.branch
    || (outlet?.branches?.length === 1 ? outlet.branches[0].id : '');
  const [services, setServices] = useState<CatalogueService[] | null>([]);
  const [packages, setPackages] = useState<CataloguePackage[]>([]);
  const [fields, setFields] = useState<VisitField[]>([]);
  // NO `recent` HERE. It was fetched on every entry to this screen and never rendered once — the
  // matches come from search-service (see the note below), so this was a request the busiest screen
  // in the product paid for and threw away, plus a state that made a reviewer believe a «عملاء
  // اليوم» strip existed. `recentCustomers` still serves «عملائي», which does show it.
  const [chosen, setChosen] = useState<string[]>([]);
  const [phone, setPhone] = useState('');
  const [name, setName] = useState('');
  const [plate, setPlate] = useState('');
  /** What he sees while typing: the same string, with the separator placed for him. */
  const [plateText, setPlateText] = useState('');
  /** Cars whose plate starts with what he has typed. Two characters are enough to narrow a yard. */
  const [plateHits, setPlateHits] = useState<CustomerHit[] | null>([]);
  /** The number the plate resolved to — and whether the operator has overridden it. */
  const [plateKnown, setPlateKnown] = useState(false);
  const [changing, setChanging] = useState(false);
  const [meter, setMeter] = useState('');
  const [note, setNote] = useState<string | null | undefined>(undefined);
  // EVERY ROW THE QUEUE HOLDS — waiting AND stuck. `subscribe` emits the whole list, so counting
  // it as "waiting to be sent" counted visits that will never be sent among them, and the number
  // an operator watched go down would have stalled at one for ever with no explanation.
  const [queued, setQueued] = useState<Queued[]>([]);
  /** The «من يحفظ؟» sheet is open. The press is held until it answers, either way. */
  const [asking, setAsking] = useState(false);
  const pending = queued.filter((r) => !r.stuck);
  const stuck = queued.filter((r) => r.stuck);
  const [matches, setMatches] = useState<CustomerHit[] | null>([]);

  // THE SERVER SAID SO. Not a rule about trades written into this file — that would be our own data
  // living where our console cannot change it (spec 13.2).
  const has = (n: string) => fields.some((f) => f.name === n);
  const showPlate = has('plate');
  const showMeter = has('meter');

  useEffect(() => {
    if (!isSignedIn(session)) return;
    fetchCatalogue(session)
      .then((r) => { setServices(r.services); setPackages(r.packages ?? []); setFields(r.fields ?? []); })
      .catch(() => { setServices(null); setPackages([]); setFields([]); });
    // THE EARNING RULES, ONCE. A failure leaves the tiles without numbers rather than with zeros:
    // a shop that has not set points up must not be shown sixteen zeros, and a shop that has must
    // not be shown zeros because one read failed.
    earnSettings(session).then(setEarn).catch(() => setEarn(null));
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

  /** WHICH PACKAGE THIS VISIT SELLS — see `VisitDraft.package_id`'s own docstring for why this is
   *  attribution, not a second source of truth: `chosen` still carries the package's real
   *  component services either way, exactly as it would if he had tapped each of them by hand. */
  const [selectedPackageId, setSelectedPackageId] = useState('');
  const selectPackage = useCallback((pkg: CataloguePackage) => {
    setChosen((cur) => {
      if (selectedPackageId === pkg.id) {
        // TAPPED AGAIN — undo exactly what selecting it added, nothing he chose separately.
        return cur.filter((id) => !pkg.service_ids.includes(id));
      }
      // A PREVIOUSLY SELECTED PACKAGE STEPS ASIDE FIRST. A visit sells one package at a time; a
      // second tap replaces the first rather than stacking two bundles' worth of services with no
      // way to tell which is which.
      const previous = packages.find((p) => p.id === selectedPackageId);
      const withoutPrevious = previous
        ? cur.filter((id) => !previous.service_ids.includes(id))
        : cur;
      return [...new Set([...withoutPrevious, ...pkg.service_ids])];
    });
    setSelectedPackageId((cur) => (cur === pkg.id ? '' : pkg.id));
  }, [packages, selectedPackageId]);

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
        .catch(() => { if (!stale) setMatches(null); });
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
  const [offer, setOffer] = useState<FieldOffer | null | undefined>(undefined);
  /**
   * WHAT HE HAS, AND WHAT HE CAN SPEND IT ON — beside the offer, from the same lookup.
   *
   * ONE by-phone CALL FOR BOTH. The offer and the balance are both keyed by the pseudonym, and
   * two lookups for one number would double a request that sits inside a five-second journey.
   */
  const [subject, setSubject] = useState('');
  const [balance, setBalance] = useState<Balance | null | undefined>(undefined);
  const [earn, setEarn] = useState<EarnSettings | null | undefined>(undefined);
  const [redeeming, setRedeeming] = useState('');
  /** The idempotency key of each redemption in flight, by (customer, reward) — see `spend`. */
  const attempts = useRef<Record<string, string>>({});
  // THE MANAGER'S NAME, asked for only where the shop's own rule requires it. Kept as the id of
  // the reward being approved so the box appears under that one tile and nowhere else — a field
  // that is always on the screen is a field the counter learns to fill with anything.
  const [approving, setApproving] = useState('');
  const [approvedBy, setApprovedBy] = useState('');
  /**
   * WHETHER THE OPERATOR SAID THE CUSTOMER TOOK HIS OFFER.
   *
   * Held on the screen until the visit is saved, because the offer is applied TO a visit and the
   * visit does not exist until he presses save. Consuming it earlier would spend an entitlement
   * against something that may never be recorded.
   */
  const [applying, setApplying] = useState(false);
  const [redeemed, setRedeemed] = useState<string | null | undefined>(undefined);

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
  const spend = useCallback(async (rewardId: string, rewardName: string, approver = '') => {
    if (!subject || redeeming) return;
    setRedeeming(rewardId);
    // ONE KEY PER INTENT, NOT PER PRESS (د-12).
    //
    // `redeem` used to mint a key inside itself, so a retry was a NEW redemption to the server.
    // The phone loses signal after the request arrived: the points are already spent, the screen
    // says «تعذّر», the cashier presses again with the customer watching — and the balance is
    // deducted twice while two receipts go out. The visit queue learned this first; the same rule
    // applies to the one act on this screen that moves a customer's balance.
    //
    // KEPT UNTIL IT SUCCEEDS, and cleared only then: every attempt at THIS reward for THIS
    // customer carries the same key, so the server answers a repeat as the duplicate it is.
    const intent = `${subject}:${rewardId}`;
    const idem = attempts.current[intent] ?? newIdempotencyKey();
    attempts.current[intent] = idem;
    try {
      await redeem(session, subject, rewardId, idem, approver);
      delete attempts.current[intent];
      setRedeemed(rewardName);
      setApproving('');
      setApprovedBy('');
      setBalance(await balanceFor(session, subject));
      window.setTimeout(() => setRedeemed(null), 4000);
    } catch (e) {
      // THE SENTENCE THE SERVICE WROTE — which this line PROMISED and did not deliver.
      //
      // `api.ts` throws an ApiError whose `.message` is built for a log: `POST /api/v1/loyalty/
      // redeem → 400`. So the cashier, with the customer in front of him, read a route and a
      // number instead of «رصيد العميل لا يكفي» — the sentence loyalty was changed to RETURN
      // rather than raise for exactly this moment. `sentenceFor` reads the body the service sent.
      setNote(sentenceFor(e, t('visit.error.redeemFailed')));
      window.setTimeout(() => setNote(null), 4000);
    } finally {
      setRedeeming('');
    }
  }, [redeeming, session, subject]);

  // TEN DIGITS STARTING 05, WHICH IS WHAT A SAUDI MOBILE IS. The old check was `length >= 9`, so
  // a nine-digit typo saved happily and the reminder went nowhere for ever — nothing failed, and
  // the shop learned about it the day a customer said he never hears from them.
  const phoneOk = /^05\d{8}$/.test(phone);
  // WHAT THE SAVE REQUIRES, WHICH IS NOT THE SAME QUESTION. `phoneOk` asks «can a reminder reach
  // this number», and that is worth saying loudly — the check exists because a nine-digit typo
  // used to save happily and the reminder went nowhere for ever, silently.
  //
  // BUT IT WAS ALSO THE GATE ON THE BUTTON, AND THAT REFUSED REAL CUSTOMERS. A visitor with a
  // Gulf number, a company landline, a number typed with its country code — all of them left the
  // save button dark, with no message, on the screen used a hundred times a day. And it is this
  // screen alone: `operations/api/v1/field.py` accepts three characters, `till.py` accepts a visit
  // with NO phone at all, and `_normalise_phone` says in writing that anything which is not a
  // Saudi mobile «is stored as typed rather than refused… refusing it would stop a real visit
  // being recorded to enforce a format nobody promised». Three lines below, the plate rule says
  // exactly the same thing about plates. One screen, two doctrines.
  //
  // So the button now asks what the SERVICE asks, and the unusual number is reported rather than
  // rejected: he can serve the customer, and he can see that this one will not get reminders.
  // `fixtures/phones.json` holds the cases and both sides read it.
  const phoneUsable = phone.trim().length >= 3;
  // THE PLATE IS REQUIRED WHERE THE SHOP SERVES CARS — one letter and one digit, in either script.
  // The shop says so itself now, with the «خدماتي على السيارات» switch; it used to be inferred
  // from a trade we no longer ask for and no longer store.
  // A tyre shop that saves a visit with the box empty has recorded a row its own counter cannot
  // find again: that screen looks a car up by plate before it looks a person up by phone.
  //
  // WE DO NOT CHECK THE SAUDI FORMAT, and the server does not either (operations/core/plate.py):
  // temporary, transit, Gulf and diplomatic plates are all real and none of them matches it, and a
  // refusal the operator cannot satisfy with a customer waiting becomes «1» typed into the box.
  // arabic-indic-digits: intentional — a plate is typed on an Arabic keyboard as often as a
  // Latin one, and operations normalises both to 0-9. Refusing them here would refuse a
  // correct plate at the one screen used a hundred times a day.
  const plateOk = !showPlate || (/[0-9٠-٩]/.test(plate) && /\p{L}/u.test(plate));
  const ready = chosen.length > 0 && phoneUsable && plateOk;

  /**
   * EVERYTHING THE SAVE DOES ONCE THE «WHO» IS SETTLED — proved or deliberately skipped.
   *
   * Split out of `save` because the answer to «من يحفظ؟» arrives from a sheet, one render later:
   * the press cannot both ask and commit, and holding the entry in state until the answer comes
   * back is what lets «تخطّي» and «تأكيد» end in the same place.
   */
  const commit = useCallback(() => {
    // MINTED HERE, ONCE PER SAVE. Not inside the queue and not inside the request — a key created
    // where the request is sent would be a new key on every retry, which is exactly no key.
    const key = newIdempotencyKey();
    const who = proof();
    // THE OFFER TRAVELS WITH THE VISIT, NOT BESIDE IT (ط-1). Calling `applyOffer` here, alongside
    // `queue.add`, raced the very request the queue was about to send: the server has no visit to
    // attach an offer to until `recordVisit` has landed, and the two calls reached it in whatever
    // order the network gave them — a race the operator's own «تم الحفظ ✓» told him he had won.
    // Passing the pseudonym into the queue lets it apply the offer only once THIS visit is
    // confirmed recorded — see queue.ts.
    queue.add({
      phone,
      service_ids: chosen,
      name: name.trim() || undefined,
      plate: showPlate && plate.trim() ? plate.trim() : undefined,
      meter: showMeter && meter ? Number(meter) : undefined,
      package_id: selectedPackageId || undefined,
      idempotency_key: key,
      // EMPTY IS AN ANSWER. He skipped, or nobody in this shop has a PIN — and a visit filed under
      // nobody is the truth, while a visit filed under whoever the device last remembered is the
      // defect this whole path exists to close.
      operator_id: who?.id,
      operator_ticket: who?.ticket,
    }, session, applying ? subject || undefined : undefined);
    setApplying(false);

    // CLEARED ON THE QUEUE, NOT ON THE SERVER. The next customer is already waiting; a screen that
    // held still for a round trip would spend its five-second budget on a network the operator
    // cannot see and cannot fix.
    setChosen([]);
    setSelectedPackageId('');
    setPhone('');
    setName('');
    setPlate('');
    setMeter('');
    setNote(t('visit.saved'));
    window.setTimeout(() => setNote(null), 1500);
  }, [applying, chosen, meter, name, phone, plate, selectedPackageId, session, showMeter, showPlate, subject]);

  const save = useCallback(() => {
    // A WRONG NUMBER IS REFUSED HERE AND NOWHERE ELSE, and the refusal SAYS what is wrong. Silence
    // at this point is the expensive kind: the visit looks saved, the customer is never reached,
    // and nobody learns why for months.
    if (chosen.length > 0 && showPlate && !plateOk) {
      // SAID BEFORE THE REQUEST, not after it. The server refuses this too — it must, since the
      // till and any other client reach the same endpoint — but a round trip to be told about a
      // box on the screen in front of him is a round trip that reads as a bug.
      setNote(t('visit.error.plateIncomplete'));
      window.setTimeout(() => setNote(null), 4000);
      return;
    }
    if (chosen.length > 0 && !phoneUsable) {
      setNote(t('visit.error.phoneIncomplete'));
      window.setTimeout(() => setNote(null), 4000);
      return;
    }
    if (!ready) return;
    // WHO IS SAVING, ASKED ONCE PER PROOF AND NOT ONCE PER VISIT. A live ticket goes straight
    // through, so the busy hour is uninterrupted; an expired one opens the sheet, which remembers
    // his name so re-proving is four digits.
    if (!proof()) { setAsking(true); return; }
    commit();
  }, [chosen, commit, phoneUsable, plateOk, ready, showPlate]);

  if (!isSignedIn(session)) {
    // SAYS SO PLAINLY RATHER THAN INVENTING A TENANT. A placeholder establishment would let every
    // screen appear to work while writing visits into data nobody owns.
    return (
      <main className="grid min-h-dvh place-items-center bg-surface-0 p-6 text-center">
        <p className="text-lg text-text-secondary">{t('visit.notSignedIn')}</p>
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
            /* A COLUMN, AND A LIMIT ON HOW WIDE IT MAY GET. On a desk this pane spread to the full
               width of the window: a phone-number box a metre across, and keys the size of playing
               cards with a hand's worth of dead space under them. Ten digits do not need more
               width than a phone gives them — the extra pixels made every target further from the
               last one, which is slower, not roomier. */
            <div className="mx-auto flex h-full w-full max-w-sm flex-col gap-2">
              {/* A REAL INPUT, NOT A DISPLAY — and this was a defect I introduced.
                  The number used to be a <div> because the keypad below was the only way to type
                  it. Then the keypad became touch-only, correctly: it is a thumb's tool and it was
                  pushing everything below the fold on a desktop. But that left a machine with a
                  keyboard NO WAY AT ALL to enter a phone number, on the screen this product is
                  built around. Found by a screenshot of a failing test, not by the type checker —
                  nothing was broken in code, the control simply was not there. */}
              <input
                value={phone}
                onChange={(e) => setPhone(digitsOnly(e.target.value).slice(0, 10))}
                dir="ltr"
                inputMode="tel"
                autoComplete="off"
                placeholder={t('visit.phone.placeholder')}
                aria-label={t('visit.phone.ariaLabel')}
                className="h-[clamp(3rem,7dvh,3.5rem)] w-full rounded-xl bg-surface-1 px-4 text-end text-3xl font-semibold tabular-nums shadow-sm placeholder:text-text-secondary"
              />

              {/* FEEDBACK, NOT A GATE. It confirms the moment the ten digits are right and
                  counts what is missing before that — and it stops there: he can still move to
                  the services and come back, because the field is not always filled in the order
                  the screen lists it. The refusal belongs to «حفظ وإرسال», which is the moment a
                  wrong number becomes permanent. */}
              <p className={`px-1 text-sm ${phoneOk ? 'text-success' : 'text-text-secondary'}`}>
                {phone.length === 0
                  ? t('visit.phone.hint.empty')
                  : phoneOk
                    ? t('visit.phone.hint.ok')
                    : phone.length < 10
                      ? `${phone.length} ${t('visit.phone.hint.counting')}`
                      : t('visit.phone.hint.notSaudi')}
              </p>
              {/* THE KEYPAD IS FOR A THUMB, NOT FOR A DESK. On a machine with a real keyboard it
                  was a second, larger way to type ten digits — and it pushed everything that
                  matters below the fold. `.touch-only` is a pointer test, not a width test: see
                  index.css for why the width variant could not even compile here. */}
              {/* THE MATCHES, WHERE HE IS TYPING — and in a fixed slot. A list that grows pushes
                the keypad down under his thumb between one digit and the next, so the key he
                aims at is not the key he hits. The height is reserved whether or not anyone
                matches; an empty two-line gap costs nothing and a moving keypad costs a wrong
                number saved against the wrong customer. */}
            {/* IT GROWS ONLY WHEN IT HAS SOMETHING. `flex-1` made this empty box claim every
                spare pixel and push the keypad's bottom row under the arrows — a control cut in
                half is worse than one that is absent. `max-h` caps it when matches arrive and it
                takes no height at all when they have not. */}
            <div className="max-h-24 shrink-0 overflow-y-auto">
              {/* THE MATCHES APPEAR WHILE HE TYPES. Spec 4.3: whoever types five correct digits and
                  sees nothing concludes the customer is new — and registers him a second time. */}
              {(matches ?? []).length > 0 ? (
                <div className="flex flex-col gap-1">
                  {(matches ?? []).slice(0, 4).map((c) => (
                    <button
                      key={c.id}
                      type="button"
                      onClick={() => { setPhone(c.phone); setName(c.name ?? ''); }}
                      className="flex items-center justify-between rounded-xl bg-surface-1 px-3 py-2 text-start shadow-sm active:scale-95"
                    >
                      <span dir="ltr" className="tabular-nums">{asLocal(c.phone)}</span>
                      <span className="text-text-secondary">{c.name || '—'}</span>
                    </button>
                  ))}
                </div>
              ) : null}

              {/* PRESENT FROM THE FIRST VISIT, REQUIRED AT NONE (spec 4.3). No asterisk and no
                  validation: he cannot ask a stranger his name while taking his key, but after five
                  visits he knows it and writes it in a quiet moment. */}
            </div>

            {/* THE WAY BACK OUT OF AN EDIT. Pressing «تعديل» used to be one-way: the lookup stops
                running while `changing` is set, so the card never returned and he had no button
                that said so. An edit a person cannot abandon is a trap, not a feature. */}
            {changing ? (
              <button
                type="button"
                onClick={() => { setChanging(false); }}
                className="min-h-11 shrink-0 rounded-xl bg-surface-2 text-sm font-semibold"
              >
                {t('visit.cancelEdit')}
              </button>
            ) : null}

            {/* THE ON-SCREEN PAD IS GONE, BY DECISION. It was built for a wall-mounted tablet with
                no keyboard of its own; every device this actually runs on — a phone, a laptop —
                brings one, and `inputMode="tel"` above raises the numeric one on touch. So the pad
                was a second keyboard competing with the device's own, taking the bottom half of the
                screen away from the matches, which are the part he is waiting for. */}
            </div>

  );

  const perksPane = (
    <>
            {/* HIS OFFER, WHERE THE WORK HAPPENS. Directly under the number, above the matches:
                by the time it appears the number is complete, so there is exactly one person it can
                belong to. Loud on purpose — this is the sentence the customer is about to ask about,
                and a worker who misses it has taken money for something already paid for. */}
            {offer?.text ? (
              <div className="rounded-xl bg-info-soft p-3 text-info-on-soft shadow-sm">
                <div className="mb-1 flex items-center gap-1 text-sm font-semibold">
                  {t('visit.offer.title')}
                  <AssistantHint session={session} anchor="visit.offer" />
                </div>
                <div>{offer.text}</div>
                {/* THE AMOUNT, STATED. The sentence above is whatever was sent — often the
                    owner's own line, which need not name the discount at all. An operator who
                    cannot see it takes the customer's word for what he is owed. */}
                {offer.value ? (
                  <div className="mt-1 text-sm font-semibold">{t('visit.offer.discount')}: {offer.value}</div>
                ) : null}
                {offer.expires_at ? (
                  <div className="mt-1 text-sm tabular-nums opacity-80">
                    {t('visit.offer.expires')} {new Date(offer.expires_at * 1000).toLocaleDateString('ar-SA-u-ca-gregory')}
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
                  <span>{t('visit.offer.applyLabel')}</span>
                </label>
              </div>
            ) : null}

            {/* HIS POINTS, AND THE ONE TAP THAT SPENDS THEM.
                Under the offer, because an offer is already his and points are a choice he makes.
                Nothing renders without a balance: a shop with no loyalty programme must not be
                shown an empty points box on the screen it uses a hundred times a day. */}
            {balance ? (
              // A TINTED PANEL, NOT ANOTHER GREY BOX — same reasoning as Shop.tsx's own Tile:
              // "the eye sorts the row by shape/colour before it ever reads a number". On a
              // counter this pane loads a hundred times a day; a cashier recognising "this is the
              // points card" by its own colour, before reading a word of it, IS the speed — never
              // in tension with it.
              <div className="rounded-xl bg-accent-soft p-3 text-accent-on-soft shadow-sm">
                <div className="flex items-center justify-between gap-3">
                  <span className="flex items-center gap-1.5 text-sm">
                    <Gift size={15} aria-hidden />
                    {t('visit.points.balance')}
                    <AssistantHint session={session} anchor="visit.points_balance" />
                  </span>
                  <span className="tabular-nums text-xl font-bold">{balance.points} {t('visit.points.unit')}</span>
                </div>

                {redeemed ? (
                  <p className="mt-2 rounded-lg bg-success-soft p-2 text-success-on-soft">
                    {tf(t, 'visit.points.redeemed', { name: redeemed })}
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
                          onClick={() => (r.needs_approval
                            ? setApproving(r.id === approving ? '' : r.id)
                            : spend(r.id, r.name))}
                          className="flex w-full items-center justify-between gap-3 rounded-lg bg-surface-2 px-3 py-3 text-start disabled:opacity-60"
                        >
                          <span>
                            {r.name}
                            {/* SAID BEFORE THE TAP, NOT AFTER IT. The service refuses this reward
                                without a manager's name, and until this badge existed the counter
                                found that out from an error message with the customer already
                                holding out his hand (د-14أ). */}
                            {r.needs_approval ? (
                              // WARNING-TONED, NOT NEUTRAL GRAY — "this one needs a manager" is a
                              // fact that changes what the cashier does next; it must read as a
                              // different KIND of row before he reads a word of it, the same
                              // colour-before-text recognition the points card above now uses.
                              <span className="ms-2 inline-flex items-center gap-1 rounded bg-warning-soft px-1.5 py-0.5 text-xs font-medium text-warning-on-soft">
                                {t('visit.points.needsApproval')}
                                <AssistantHint session={session} anchor="visit.needs_approval" />
                              </span>
                            ) : null}
                          </span>
                          <span className="shrink-0 tabular-nums text-sm text-text-secondary">
                            {tf(t, 'visit.points.costAndRemaining', { cost: r.cost, remaining: balance.points - r.cost })}
                          </span>
                        </button>
                        {approving === r.id ? (
                          <div className="mt-2 flex gap-2">
                            <input
                              type="text"
                              value={approvedBy}
                              onChange={(e) => setApprovedBy(e.target.value)}
                              placeholder={t('visit.points.approverPlaceholder')}
                              aria-label={t('visit.points.approverPlaceholder')}
                              className="min-w-0 flex-1 rounded-lg bg-surface-2 px-3 py-2"
                            />
                            <Button
                              disabled={!approvedBy.trim() || Boolean(redeeming)}
                              onClick={() => spend(r.id, r.name, approvedBy.trim())}
                            >
                              {t('visit.points.approveAndRedeem')}
                            </Button>
                          </div>
                        ) : null}
                      </li>
                    ))}
                  </ul>
                ) : balance.to_next_reward > 0 ? (
                  // ENCOURAGEMENT, NOT AN APOLOGY — and only when there is something true to say.
                  // Zero means either he can afford everything or the shop has no rewards, and
                  // «تبقى لك 0 نقطة» is a sentence that means nothing to the person reading it.
                  <p className="mt-1 text-sm text-text-secondary">
                    {tf(t, 'visit.points.toNextReward', { n: balance.to_next_reward })}
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
  // THE PLATE ANSWERS FOR ITS OWNER. A car we have seen carries a number we already hold, so the
  // phone step is dropped from the journey exactly as the offers step is when it is empty.
  useEffect(() => {
    const p = plate.trim();
    if (!showPlate || p.length < 3) { setPlateKnown(false); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      customerByPlate(session, p)
        .then((r) => {
          if (stale || changing) return;
          const found = r.customer?.phone ?? '';
          setPlateKnown(Boolean(found));
          if (found) { setPhone(found); setName(r.customer?.name ?? ''); }
        })
        // A LOOKUP THAT FAILS ASKS FOR THE NUMBER. It never blocks and never guesses: the step
        // simply stays in the journey, which is where it was before this existed.
        .catch(() => { if (!stale) setPlateKnown(false); });
    }, 250);
    return () => { stale = true; window.clearTimeout(id); };
  }, [changing, plate, session, showPlate]);

  /**
   * WHO THE PLATE FOUND — shown, not assumed, and editable in place.
   *
   * Two things happen constantly in a workshop: a car is sold, and a man changes his number. Both
   * make our stored number wrong, and a screen that skipped straight past would save the visit
   * against the previous owner — who then gets the reminder about a car he no longer has.
   */
  const knownPane = (
    <div className="flex h-full flex-col justify-center gap-3">
      {/* SUCCESS COLOUR, NOT ANOTHER GREY CARD — this is the moment the match is confirmed, and
          the same "colour before number" rule applies: a green card says "matched, proceed" before
          a single digit is read. */}
      <div className="rounded-2xl bg-success-soft p-4 text-success-on-soft shadow-sm">
        <div className="flex items-center justify-center gap-1.5">
          <CheckCircle2 size={16} aria-hidden />
          <span className="text-xs font-medium">{t('visit.customerMatched')}</span>
        </div>
        <div dir="ltr" className="text-center text-3xl font-semibold tabular-nums">{phone}</div>
        {name ? <div className="mt-1 text-center text-lg">{name}</div> : null}
        <div className="mt-1 text-center text-sm">
          {t('visit.plate.prefix')} <span dir="ltr">{plate}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={() => {
          // THE NUMBER IS KEPT, NOT CLEARED. Emptying it turned «تعديل» into «ابدأ من الصفر»: he
          // wanted to fix one digit of a number he could no longer see, on a page that had also
          // stopped offering him a way back. Editing starts from what is there.
          setChanging(true);
          setPlateKnown(false);
        }}
        className="flex min-h-[44px] items-center justify-center gap-1.5 rounded-xl bg-surface-2 text-base font-semibold"
      >
        <Pencil size={15} aria-hidden />
        {t('visit.editCustomer')}
      </button>

      <p className="text-center text-xs text-text-secondary">
        {t('visit.editHint')}
      </p>
    </div>
  );

  /**
   * The plate, in the two halves it actually has.
   *
   * A SAUDI PLATE IS AT MOST FOUR DIGITS AND THREE LETTERS, and often fewer of either — a short
   * number is a real plate, not an unfinished one. So the digits box advances to the letters on
   * its own ONLY when it is full at four; below that he moves himself. Auto-advancing on a guess
   * would trap every owner of a two-digit plate.
   *
   * LATIN, AND UPPERCASED AS HE TYPES. Both scripts appear on the plate itself, and letting each
   * operator pick means «ABC 1234» and «ا ب ج 1234» are two customers with one car. One form is
   * stored, and the keyboard is told which one to open with `inputMode`.
   *
   * STORED AS ONE STRING, «1234 ABC», because that is what the index and the lookup already use
   * (seams.py). The split is how it is typed, not how it is kept.
   */
  useEffect(() => {
    setPlate(plateText.replace(/\s+/g, ' ').trim());
  }, [plateText]);

  /**
   * THE PARTIAL PLATE, ANSWERED WHILE HE TYPES — and this is the half that was missing.
   *
   * `by-plate` is an EXACT match (operations' store filters on equality, by design: a prefix scan
   * over the datastore is a table scan). So until the operator had typed the plate perfectly,
   * character for character, in the same script and the same order as it was stored, the screen
   * said nothing — and «سيارة معروفة» never appeared for a car we have serviced ten times. He
   * concludes the customer is new and registers him twice, which is the exact failure the phone
   * keypad has a suggest call to prevent.
   *
   * SAME MECHANISM, THEN: search-service's /suggest, which matches prefixes and already indexes
   * the plate on the customer document (seams.py). Two characters are enough to narrow a yard.
   */
  useEffect(() => {
    const p = plate.trim();
    if (!showPlate || changing || plateKnown || p.length < 2) { setPlateHits([]); return; }
    let stale = false;
    const id = window.setTimeout(() => {
      suggestByPrefix(session, p)
        .then((hits) => {
          if (stale) return;
          // ONLY THE CARS. The same index answers phone prefixes, and «12» is a plausible start
          // for both — a list of people whose NUMBER begins with what he read off a bumper is
          // noise standing between him and the one row he wants.
          setPlateHits(hits.filter((h) => h.plate).slice(0, 4));
        })
        .catch(() => { if (!stale) setPlateHits(null); });
    }, 250);
    return () => { stale = true; window.clearTimeout(id); };
  }, [changing, plate, plateKnown, session, showPlate]);

  const platePane = (
    <div className="flex h-full flex-col justify-center gap-3">
      <input
        value={plateText}
        onChange={(e) => setPlateText(formatPlate(e.target.value))}
        autoFocus
        placeholder="1234 ABC"
        aria-label={t('visit.plate.ariaLabel')}
        dir="ltr"
        className="h-[clamp(3.25rem,9dvh,4rem)] rounded-2xl bg-surface-1 px-4 text-center text-xl font-semibold uppercase tabular-nums shadow-sm placeholder:font-normal placeholder:normal-case placeholder:text-text-secondary"
      />

      {/* THE MATCHES, TAPPABLE. He read four characters off a bumper; finishing the plate by hand
          when we already hold it is work we can do for him — and one tap fills the owner too. */}
      {(plateHits ?? []).length > 0 && !plateKnown ? (
        <ul className="flex flex-col gap-2">
          {(plateHits ?? []).map((h) => (
            <li key={h.id || h.plate}>
              <button
                type="button"
                onClick={() => {
                  setPlateText(formatPlate(h.plate ?? ''));
                  if (h.phone) setPhone(h.phone);
                  if (h.name) setName(h.name);
                }}
                className="flex min-h-[44px] w-full items-center justify-between gap-3 rounded-xl bg-surface-1 px-4 shadow-sm"
              >
                <span dir="ltr" className="text-base font-semibold tabular-nums">{h.plate}</span>
                <span className="truncate text-sm text-text-secondary">
                  {h.name || <span dir="ltr">{asLocal(h.phone)}</span>}
                </span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}

      <p className="text-center text-sm text-text-secondary">
        {plateKnown && !changing
          ? t('visit.plate.hint.known')
          : (plateHits ?? []).length > 0
            ? t('visit.plate.hint.matches')
            : t('visit.plate.hint.typing')}
      </p>
    </div>
  );

  /**
   * Is there anything on the entitlements page worth turning to?
   *
   * A BALANCE HE CANNOT SPEND YET IS STILL WORTH SEEING, and this is what the gate used to get
   * wrong: it asked only whether he could afford something, so a customer with 30 points and a
   * cheapest reward of 100 had his page removed from the journey entirely. The operator could not
   * tell him where he stood, and the pane's own «تبقّى له … لأقرب مكافأة» — written precisely for
   * that moment — was unreachable code.
   *
   * WHICH IS THE POINT OF A POINTS PROGRAMME: it works on the visit BEFORE the free one. Hiding
   * the count until it is already enough removes the only thing that brings him back.
   *
   * A shop with no programme still shows nothing: `balance` is null there, and this stays false.
   */
  const hasPerks = Boolean(offer?.text)
    || Boolean(balance?.rewards?.length)
    || Boolean(balance && (balance.points > 0 || balance.to_next_reward > 0));

  const detailsPane = (
    /* THE SAME LIMIT AS THE OTHER TWO PANES, and one width wider because a tile grid genuinely
       uses it. Unbounded, this page put six services on one line across a desktop and left two
       thirds of the window empty under them — the eye travels the whole width to read a menu that
       would read better in three columns. */
    <div className="mx-auto flex w-full max-w-2xl flex-col">
      {/* WHAT HE TOOK — the last page, and the one he spends the most time on. */}
      {/* AND ONE TAP TO UNDO ALL OF IT. A customer changes his mind and walks out with the car
          half-quoted; without this the operator un-taps six tiles one by one while the next car
          waits. It only appears when there is something to clear — a button that does nothing is
          a button he has to think about every time he passes it. */}
      {chosen.length > 0 ? (
        <div className="mb-2 flex items-center justify-between gap-2">
          <span className="text-sm text-text-secondary tabular-nums">
            {tf(t, 'visit.chosen.count', { n: chosen.length })}
          </span>
          <button
            type="button"
            onClick={() => { setChosen([]); setSelectedPackageId(''); }}
            className="min-h-[44px] rounded-xl bg-surface-2 px-4 text-sm font-semibold"
          >
            {t('visit.chosen.clear')}
          </button>
        </div>
      ) : null}
      {/* AND THE SECOND TAP, WHICH IS THE WHOLE RULE (§5.6.2). The badge SAYS what is available;
          this applies it. «الصمت لا يصرف» — a customer who came for something else and was
          quietly charged an offer he was saving is a customer we took something from, and he may
          be holding it for next month. So it appears only when a marked service is chosen, and
          ignoring it is a legitimate answer: he may be collecting points on purpose. */}
      {(() => {
        const markedOffer = chosen.some((id) => (offer?.service_ids ?? []).includes(id));
        const spendable = (balance?.rewards ?? []).filter(
          (r) => r.service_id && chosen.includes(r.service_id),
        );
        if (!markedOffer && spendable.length === 0) return null;
        return (
          <div className="mb-2 flex flex-wrap items-center gap-2 rounded-xl bg-info-soft px-3 py-2">
            <span className="text-sm text-info-on-soft">{t('visit.chosen.appliesTo')}</span>
            {markedOffer ? (
              <Button
                onClick={() => setApplying(true)}
                variant={applying ? 'solid' : 'ghost'}
              >
                {applying ? t('visit.applyOffer.applied') : t('visit.applyOffer.apply')}
              </Button>
            ) : null}
            {/* THE ONE-TAP STRIP CARRIES ONLY WHAT ONE TAP CAN ACTUALLY DO. A reward above the
                shop's threshold needs a manager's name, and there is nowhere here to type one —
                it stays in the sheet above, which has the box. Offering it here would be a button
                that refuses every time it is pressed. */}
            {spendable.filter((r) => !r.needs_approval).map((r) => (
              <Button
                key={r.id}
                variant="ghost"
                disabled={Boolean(redeeming) || redeemed === r.id}
                onClick={() => spend(r.id, r.name)}
              >
                {redeemed === r.id
                  ? tf(t, 'visit.redeem.done', { name: r.name })
                  : tf(t, 'visit.redeem.action', { name: r.name, cost: r.cost })}
              </Button>
            ))}
          </div>
        );
      })()}

      {/* THE BADGES COME FROM WHAT WE ALREADY ASKED FOR. His offer names the services it covers
          (§5.6.2 — the scope applies, the text persuades), and the balance names the rewards he
          can afford right now, each of which may BE a service («غسلة مجانية» is the wash, §9.4).
          No new call: the same two answers the page already holds, put where the decision is. */}
      <ServiceGrid
        session={session}
        // `?? []` AND NOT A LIE: the grid renders nothing when the catalogue could not be read,
        // and the sentence above it — which the screen already shows on an unreadable read — is
        // what tells the worker why. An empty grid with no sentence would read as «this shop sells
        // nothing», which is the failure this whole pass is about.
        services={services ?? []}
        selected={chosen}
        onToggle={toggle}
        packages={packages}
        selectedPackageId={selectedPackageId}
        onSelectPackage={selectPackage}
        offered={new Set(offer?.service_ids ?? [])}
        redeemable={new Set(
          (balance?.rewards ?? []).map((r) => r.service_id ?? '').filter(Boolean),
        )}
        points={pointsByService(earn ?? null, (services ?? []).map((x) => x.id))}
      />

      {/* WHY HE NEVER SAW AN OFFERS PAGE. Skipping a step silently makes an operator wonder what
          he missed — and «لا عروض» is the wrong answer for a customer we have never met, and a
          lie when we simply could not ask. Three facts, three sentences. */}
      {!hasPerks && phone.length >= 9 ? (
        <p className="mb-2 rounded-xl bg-surface-2 px-3 py-2 text-sm text-text-secondary">
          {perks === 'failed'
            ? t('visit.perks.failed')
            : subject
              ? t('visit.perks.none')
              : t('visit.perks.newCustomer')}
        </p>
      ) : null}
            {/* SEPARATED FROM THE TILES. Glued directly under the grid it read as another tile
                that had lost its border — a text box and a row of buttons need a gap between them
                or they look like one broken control. */}
            <div className="mt-4 flex flex-col gap-2 border-t border-border-subtle pt-4">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t('visit.name.placeholder')}
                className="h-14 rounded-xl bg-surface-1 px-4 text-lg shadow-sm placeholder:text-text-secondary"
              />

              {showMeter ? (
                <input
                  value={meter}
                  onChange={(e) => setMeter(digitsOnly(e.target.value))}
                  inputMode="numeric"
                  placeholder={t('visit.meter.placeholder')}
                  dir="ltr"
                  className="h-14 rounded-xl bg-surface-1 px-4 text-lg tabular-nums shadow-sm placeholder:text-text-secondary"
                />
              ) : null}
            </div>
    </div>
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
            it. Recent customers live in «عملائي», where looking someone up is the point.

            THE STRIP BELOW IS A DIFFERENT THING ENTIRELY (§6.3, docs/وصف-تطبيق-الحجوزات.md,
            Stage 9): today's BOOKINGS, not recent customers — a person the operator ALREADY
            knows is coming, at a time she already knows. One tap opens the visit outright rather
            than shortcutting a lookup, which is why the reasoning above does not apply to it. */}
        {branchScopeId ? (
          <TodayBookingsStrip session={session} branchId={branchScopeId} services={services ?? []} />
        ) : null}

        {/* ── THE JOURNEY ───────────────────────────────────────────────────────────────────
            One question per screen, moved by a thumb. In a shop that works on cars the plate comes first
            and alone: the car rolls in and that is what is read off it. Everywhere else the
            person IS the phone number, so that is the first screen instead.

            THE ENTITLEMENTS STEP IS ABSENT WHEN THERE IS NOTHING IN IT, and the step after says
            which kind of nothing it was — a new customer is not a customer with no offers, and
            neither is a lookup we could not complete. */}
        <Steps
          steps={[
            ...(showPlate
              ? [{ id: 'plate', title: t('visit.step.plate'), body: platePane }]
              : []),
            // TWO FACES, NOT TWO OUTCOMES. When the plate already answered, this page STAYS and
            // shows who it found — the operator has to be able to see that the car in front of him
            // belongs to the number about to be saved. Skipping it outright hid exactly the thing
            // he would want to check, and left a sold car quietly reminding its previous owner.
            { id: 'who', title: showPlate ? t('visit.step.carOwner') : t('visit.step.customerPhone'),
              body: plateKnown && !changing ? knownPane : identityPane },
            { id: 'perks', title: t('visit.step.perks'),
              // ASKING KEEPS THE STEP. Removing it the instant a request goes out and restoring it
              // when the answer lands moves the ground under a thumb already in motion.
              when: perks === 'asking' || hasPerks,
              body: perksPane },
            { id: 'what', title: t('visit.step.services'), body: detailsPane },
          ]}
          // THE SAVE BAR LIVES INSIDE THE JOURNEY, and it used to sit after it. That is what pushed
          // the arrows below the fold: the pane sized itself to the window while a second bar was
          // still stacked underneath, so the one control the whole screen exists for was reachable
          // only by scrolling — on a screen built expressly not to scroll.
          done={(
    <div className="flex items-center gap-3">
          {pending.length > 0 ? (
            <span className="inline-flex shrink-0 items-center gap-1 text-sm text-text-secondary tabular-nums">
              {tf(t, 'visit.pending', { n: pending.length })}
              <AssistantHint session={session} anchor="visit.pending_queue" />
            </span>
          ) : null}
          {/* AND THE ONES THAT WILL NEVER GO. The queue has always told these apart — a 400, a 403
              or a 404 is not a network to wait out, and retrying it for ever burns battery and
              hides the problem — but it told nobody: the visit left the screen, the counter said
              nothing, and a shop lost a customer with no reminder, no points and no metric, in
              silence. That silence was the whole reason for holding it rather than dropping it. */}
          {stuck.length > 0 ? (
            <span className="inline-flex shrink-0 items-center gap-1 text-sm text-danger tabular-nums">
              {tf(t, 'visit.stuck', { n: stuck.length })}
              <AssistantHint session={session} anchor="visit.stuck_queue" />
            </span>
          ) : null}
          {note ? <span className="shrink-0 text-sm text-text-secondary">{note}</span> : null}
          <button
            type="button"
            onClick={save}
            disabled={!ready}
            className="h-11 flex-1 rounded-xl bg-accent text-base font-bold text-white shadow-glow transition-transform active:scale-[0.98] disabled:opacity-40 disabled:shadow-none"
          >
            {t('visit.save')}
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

      {/* BOTH ANSWERS END IN THE SAME SAVE. «تأكيد» attaches the ticket, «تخطّي» files the visit
          under nobody — and neither leaves the operator holding a screen that will not commit. */}
      <WhoIsSaving
        session={session}
        open={asking}
        onProved={() => { setAsking(false); commit(); }}
        onSkip={() => { setAsking(false); commit(); }}
      />
    </main>
  );
}

