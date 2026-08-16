/**
 * Who is saving, and the proof of it — held for as long as the proof is good and no longer.
 *
 * WHY THIS EXISTS (أ-2). `POST /visits` has accepted `operator_id` since the day it was written,
 * `/operators/verify-pin` has been able to confirm one for just as long, and NO SCREEN HAS EVER
 * CALLED EITHER. So every visit taken on a phone carried an empty operator — and `_branch_for`
 * reads exactly that field to decide which branch the work belongs to. The consequences all landed
 * somewhere else: the branch comparison table was a column of zeros on a chain that bought
 * branches, `customer.last_branch_id` was never written so a branch campaign found nobody, and
 * «من صرف نقاط هذا العميل؟» had no answer.
 *
 * KEPT IN MEMORY AND IN sessionStorage — not localStorage. A tab reload mid-shift must not throw
 * the proof away, and a device that has been closed and reopened is a device somebody else may be
 * holding. The ticket expires on its own either way; this only decides how long a live one
 * survives the browser.
 *
 * AND IT EXPIRES ON PURPOSE, at five minutes. Re-entering four digits is a real cost on a screen
 * used a hundred times a day, and it is the whole price of the attribution: a ticket that lasted a
 * shift would let a tablet left on the counter file work all evening under the name of somebody
 * who went home. The sheet remembers WHICH operator, so re-proving is four digits and no picking.
 */
const KEY = 'raje3.field.operator.v1';

export interface Proof {
  id: string;
  name: string;
  ticket: string;
  /** Wall-clock ms after which the ticket no longer proves anything. */
  until: number;
}

/** Who was last confirmed on this device, proof or not — so the sheet opens on his name. */
export interface LastSeen {
  id: string;
  name: string;
}

let held: Proof | null = null;

function read(): Proof | null {
  if (held) return held;
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const row = JSON.parse(raw) as Proof;
    held = row && typeof row.ticket === 'string' ? row : null;
  } catch {
    // A corrupt store loses the attribution, never the visit.
    held = null;
  }
  return held;
}

/** The proof, if there is one and it is still good. Null is an ordinary answer here. */
export function proof(now = Date.now()): Proof | null {
  const row = read();
  return row && row.until > now ? row : null;
}

/** Who to open the sheet on — outlives the ticket, because his name is not a secret. */
export function lastSeen(): LastSeen | null {
  const row = read();
  return row ? { id: row.id, name: row.name } : null;
}

export function remember(id: string, name: string, ticket: string, ttlSeconds: number): Proof {
  // A SECOND OFF THE TTL WE WERE GIVEN, so a save started at the last instant is not refused by
  // the clock while it is in flight. The server's window is the authority; this only stops us
  // from sending something we already know is spent.
  const until = Date.now() + Math.max(0, ttlSeconds - 1) * 1000;
  held = { id, name, ticket, until };
  try {
    sessionStorage.setItem(KEY, JSON.stringify(held));
  } catch {
    // Quota, or a private-mode tab. The proof still holds in memory for this page.
  }
  return held;
}

export function forget(): void {
  held = null;
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing to do, and nothing worth telling the operator about.
  }
}
