/**
 * THE VISIT SURVIVES THE NETWORK — because in this trade the network is the thing that fails.
 *
 * A بنشر has a metal roof and a pit. A salon has a back room. The tablet loses signal for thirty
 * seconds several times a day, and the operator does not know it has: he taps the services, taps
 * save, hands back the keys, and the customer drives away. If the request went nowhere, so did the
 * visit, the reminder, and the reason the shop pays us.
 *
 * SO SAVING IS A LOCAL WRITE FIRST AND A REQUEST SECOND. The screen clears the instant the visit
 * is in this queue — never when the server answers — and the queue drains behind him. He is never
 * asked to wait for a network he cannot see and cannot fix.
 *
 * THE DANGER THIS DESIGN CREATES, AND HOW IT IS PAID FOR. A queue that retries is a queue that
 * sends the same visit twice: once when the request actually succeeded but the answer was lost,
 * and again when the tab is reopened. Every entry therefore carries the key minted when the
 * operator pressed save — the SAME key on every retry, for ever — and the server answers the
 * repeat with `duplicate: true` instead of creating a second visit. Without that key this file
 * would be a machine for sending duplicate WhatsApp messages the establishment pays for.
 *
 * AND IT NEVER SILENTLY GIVES UP. An entry that has failed for a reason retrying cannot fix is
 * held and surfaced, not dropped — a queue that quietly discards work is worse than one that
 * never ran, because the shop believes the visits are recorded.
 */
import type { Session } from './session';
import { ApiError, applyOffer, recordVisit, type MutualBenefitGrantAck, type VisitDraft } from './api';

const KEY = 'raje3.field.queue.v1';

export interface Queued {
  draft: VisitDraft;
  /** When the operator pressed save — his clock, kept so a visit drained an hour later is not
   *  recorded as having happened an hour late. */
  at: number;
  attempts: number;
  /** Set when the server refused for a reason a retry cannot fix. The entry stays, and the screen
   *  can show it: silently dropping it would tell the shop a visit was recorded that was not. */
  stuck?: string;
  /**
   * THE PSEUDONYM TO SPEND AN OFFER AGAINST — set only when the operator checked «طبّق العرض»
   * (ط-1). It travels WITH the visit rather than firing beside it: `applyOffer` used to be called
   * in the same breath as `queue.add`, racing the request this queue was about to make. The two
   * requests reach the server in whatever order the network gives them, and the server has no
   * visit to attach an offer to until `recordVisit` has actually landed — so the tap that read
   * «تم الحفظ ✓» silently lost the discount on every single save, worse still when offline, where
   * `applyOffer` fired against a visit that had not been sent yet and could not exist for minutes.
   *
   * SO IT WAITS ITS TURN IN THE SAME QUEUE, applied only after `recordVisit` for THIS row has
   * actually succeeded — never before, never in parallel.
   */
  applyOfferSubject?: string;
}

function load(): Queued[] {
  try {
    const raw = localStorage.getItem(KEY);
    const rows = raw ? JSON.parse(raw) : [];
    return Array.isArray(rows) ? rows : [];
  } catch {
    // A corrupt store must not take the screen down. Losing the queue is bad; a shop that cannot
    // record anything at all until somebody clears browser storage is worse.
    return [];
  }
}

function save(rows: Queued[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(rows));
  } catch {
    // Quota exhausted. Nothing useful to do here and nothing to hide: the caller already holds the
    // entry in memory for this drain, and the next successful write trims the backlog.
  }
}

/** A retry can fix a network failure, a timeout, a 502 and a 500. It cannot fix a 400 (this body
 *  is wrong), a 403 (this operator may not), or a 404 — those are stuck, and retrying them for
 *  ever burns battery and hides the real problem. 401 is NOT stuck: the token will be refreshed. */
function retriable(e: unknown): boolean {
  if (!(e instanceof ApiError)) return true;      // no response at all — the network
  if (e.status === 401) return true;
  if (e.status === 429) return true;
  return e.status >= 500;
}

export class VisitQueue {
  private rows: Queued[] = load();
  /** The drain in flight, or null. A PROMISE rather than a boolean — see `drain`. */
  private running: Promise<void> | null = null;
  private listeners = new Set<(rows: Queued[]) => void>();
  /** A SEPARATE channel from `listeners` (queue ROW state) on purpose — a celebration is a
   *  one-shot EVENT ("this visit just earned a partner reward"), not a state a re-render should
   *  replay every time the queue's row list changes for an unrelated reason. Fired only for a
   *  row that drains WHILE a listener is actually subscribed — the ordinary online case, which is
   *  the only case a celebration makes sense for: a visit that drains later, unattended, means the
   *  customer already left, and showing it to whoever opens the screen next would celebrate a
   *  stranger's visit. */
  private celebrationListeners = new Set<(grant: MutualBenefitGrantAck) => void>();

  /** Take the visit. Returns immediately — the caller clears the screen on THIS, never on a
   *  server answer, because the five-second budget cannot contain a round trip on a bad link.
   *
   *  `applyOfferSubject`, WHEN GIVEN, IS NOT SENT HERE (ط-1). It is carried on the row and spent
   *  only once `recordVisit` for this same row has actually succeeded — see `run`. */
  add(draft: VisitDraft, session: Session, applyOfferSubject?: string): void {
    const at = Date.now();
    // AND THE MOMENT GOES WITH IT (أ-3). `at` was recorded here from the first day, with the note
    // above saying exactly why — and it was never put on the request, so the server read no
    // `occurred_at` and answered «now». A workshop that lost coverage at noon had nine visits all
    // recorded at eight in the evening: «أوقات الذروة» named the reconnection, the reminders were
    // scheduled from it, and the visit confirmation reached a customer seven hours after he left.
    this.rows = [...this.rows,
                 { draft: { ...draft, occurred_at: Math.floor(at / 1000) }, at, attempts: 0,
                   applyOfferSubject: applyOfferSubject || undefined }];
    save(this.rows);
    this.emit();
    // THE SESSION IS PASSED IN, NEVER HELD. This queue outlives a token — an entry written before
    // lunch may drain after a refresh — so keeping the token it was created with would mean
    // draining with a credential that expired hours ago, and every retry answering 401.
    void this.drain(session);
  }

  pending(): Queued[] {
    return this.rows.filter((r) => !r.stuck);
  }

  stuck(): Queued[] {
    return this.rows.filter((r) => r.stuck);
  }

  subscribe(fn: (rows: Queued[]) => void): () => void {
    this.listeners.add(fn);
    return () => this.listeners.delete(fn);
  }

  subscribeToCelebrations(fn: (grant: MutualBenefitGrantAck) => void): () => void {
    this.celebrationListeners.add(fn);
    return () => this.celebrationListeners.delete(fn);
  }

  private emit(): void {
    for (const fn of this.listeners) fn(this.rows);
  }

  private emitCelebration(grant: MutualBenefitGrantAck): void {
    for (const fn of this.celebrationListeners) fn(grant);
  }

  /**
   * Send what is waiting, oldest first.
   *
   * ONE AT A TIME AND IN ORDER. Firing the backlog in parallel would put ten requests on a link
   * that just proved it cannot carry one, and would record this morning's visits after this
   * afternoon's. The order is also the shop's order, and a visit history that disagrees with what
   * the operator remembers is a support call.
   *
   * NOT REENTRANT — `focus`, `online` and a fresh save all arrive within the same second, and two
   * drains running together would send the same entry twice, surviving only on the idempotency
   * key, which is a guard we should not be spending here.
   *
   * AND A SECOND CALLER JOINS THE DRAIN RATHER THAN BEING TOLD "no". A boolean flag with an early
   * return looked equivalent and was not: awaiting it returned instantly while the real drain was
   * still in flight, so a caller who waited had not waited. Caught by a test that awaited a drain
   * and then found the queue still full — the same shape as an app that reports "sent" too early.
   */
  drain(session?: Session): Promise<void> {
    if (!session) return Promise.resolve();
    if (this.running) return this.running;
    this.running = this.run(session).finally(() => { this.running = null; });
    return this.running;
  }

  private async run(session: Session): Promise<void> {
    {
      for (const row of [...this.rows]) {
        if (row.stuck) continue;
        try {
          const ack = await recordVisit(session, row.draft);
          this.rows = this.rows.filter((r) => r !== row);
          if (ack.mutual_benefit_grant) this.emitCelebration(ack.mutual_benefit_grant);
          if (row.applyOfferSubject) {
            // ONLY NOW DOES THE VISIT EXIST ON THE SERVER (ط-1) — `ack.visit.id` names it, so
            // there is nothing left to race. STILL FIRE-AND-FORGET: the operator moved on the
            // moment `add` returned, and this queue is not the place to surface a spend failure —
            // the offer stays live and can be tapped again on the customer's next visit.
            void applyOffer(session, row.applyOfferSubject, String(ack.visit.id))
              .catch(() => undefined);
          }
        } catch (e) {
          row.attempts += 1;
          if (!retriable(e)) {
            row.stuck = e instanceof ApiError ? String(e.status) : 'unknown';
          } else {
            // STOP AT THE FIRST FAILURE. If this one could not go, neither can the next — and
            // walking the rest only to fail identically wastes the battery of a device that is
            // on a workbench all day.
            break;
          }
        } finally {
          save(this.rows);
          this.emit();
        }
      }
    }
  }
}

export const queue = new VisitQueue();

/**
 * A visit's identity, minted once when the operator presses save.
 *
 * `crypto.randomUUID` where it exists, and a composed fallback where it does not — an older tablet
 * on a workbench is exactly the device this app is for, and a missing API there must not become an
 * exception on the one path that matters.
 */
export function newIdempotencyKey(): string {
  const c = globalThis.crypto as Crypto | undefined;
  if (c?.randomUUID) return c.randomUUID();
  const rand = c?.getRandomValues
    ? Array.from(c.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, '0')).join('')
    : Math.random().toString(16).slice(2);
  return `${Date.now().toString(16)}-${rand}`;
}
