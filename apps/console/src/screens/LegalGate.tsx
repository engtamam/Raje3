/**
 * The legal gate — the one screen the owner did not ask for and cannot skip.
 *
 * PDPL Art. 6 is a consent that must be DEMONSTRABLE, and an acceptance we cannot show a version
 * for is not one. So this is not a checkbox on a signup form: the server decides what is
 * outstanding, the person reads what is actually in force at that moment, and the acceptance is
 * pinned to the version in force. A later publish correctly makes it stale and this reappears.
 *
 * THE ONE COMPOSED URL OUTSIDE THE DOOR, AND IT IS SANCTIONED RATHER THAN SMUGGLED. Every control
 * in this app is an action from the catalogue; `GET /me/legal/outstanding` is not in the catalogue
 * and by design — compliance-service lists it in `UNDECLARED_ROUTES` with the reason: "the app
 * shell calls this automatically right after login to decide whether to block on a re-acceptance —
 * a gate check the shell drives, not a button a user clicks". The ACCEPTANCE, which is a button a
 * person clicks, IS an action (`compliance.accept_legal`) and goes through the catalogue like
 * everything else.
 *
 * AND NOTHING OUTSTANDING RENDERS NOTHING. Not a "you are up to date" screen — an owner opening
 * his shop's dashboard has no use for a page confirming he agreed to something.
 */
import { useCallback, useEffect, useState, type ReactNode } from 'react';
import { AcceptTerms, type OutstandingDoc } from '@base-ui/auth/AcceptTerms';
import { AGREED_KEY } from '../auth';
import { action, call, type Catalog } from '../catalog';
import { announceExpiry } from '../expired';
import type { Session } from '../session';

const BASE = (import.meta.env.VITE_API_BASE ?? '').replace(/\/$/, '');

export function LegalGate({
  session, catalog, children,
}: {
  session: Session;
  catalog: Catalog;
  children: ReactNode;
}) {
  const [outstanding, setOutstanding] = useState<OutstandingDoc[] | null>(null);

  const load = useCallback(async () => {
    const res = await fetch(
      `${BASE}/api/v1/compliance/me/legal/outstanding?locale=ar`,
      { headers: { Authorization: `Bearer ${session.token}` } },
    );
    // 401 IS THE SESSION, NOT THE DOCUMENTS — announced once, and the app shows the door.
    if (res.status === 401) announceExpiry();
    if (res.status === 401 || res.status === 403) {
      // NOT AN ANSWER ABOUT THE DOCUMENTS. A shop provisioned before `compliance.self` was added
      // to the roles cannot ask this question at all — and treating that as "nothing outstanding"
      // is the honest direction: we do not know, and locking a paying owner out of his product on
      // an inconclusive read turns one gap into a total outage. The server still refuses anything
      // that genuinely requires an acceptance.
      return [];
    }
    if (!res.ok) throw new Error(String(res.status));
    const body = (await res.json()) as { outstanding?: OutstandingDoc[] };
    return body.outstanding ?? [];
  }, [session]);

  const accept = action(catalog, 'compliance.accept_legal');
  // THE ID, NOT THE OBJECT. `action()` returns a fresh object on every render, so listing it in the
  // dependency array re-ran the effect on every render — which fetched, which set state, which
  // rendered, for ever. The browser console filled with the same 403 dozens of times a second and
  // the screen looked merely broken. A primitive cannot cause that.
  const acceptId = accept?.id ?? '';

  useEffect(() => {
    // A FAILURE OPENS THE GATE, and that is the deliberate direction. compliance-service being
    // unreachable is not evidence that this owner owes an acceptance, and blocking a paying shop
    // out of its own product on an inconclusive read would turn one service's outage into a total
    // one. The acceptance is re-checked on the next load, and the server refuses anything that
    // actually requires it regardless of what this screen rendered.
    load()
      .then(async (docs) => {
        // HE ALREADY ANSWERED, THIRTY SECONDS AGO. The signup form gated its button on a consent
        // box with links to these very documents, so asking again is not diligence — it is a
        // second door in the same doorway, and the first thing a new owner meets.
        //
        // THE RECORD IS STILL WRITTEN HERE, against the version in force and through the declared
        // action. What the marker saves is the QUESTION, never the evidence: without these calls
        // there would be a person inside the product and nothing to show he ever agreed.
        let agreed = '';
        try { agreed = localStorage.getItem(AGREED_KEY) || ''; } catch { agreed = ''; }
        if (!agreed || !docs.length || !accept) return docs;
        try {
          for (const doc of docs) await call(session, accept, { doc_id: doc.doc_id });
        } catch {
          // The consent was real; recording it failed. Fall through and ASK — an unrecorded
          // acceptance is not an acceptance, and the honest cost is one extra screen.
          return docs;
        }
        try { localStorage.removeItem(AGREED_KEY); } catch { /* private mode */ }
        return [];
      })
      .then(setOutstanding)
      .catch(() => setOutstanding(null));
    // `accept` is deliberately absent: it is read through a ref-stable id, and the object itself
    // changes identity on every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [load, acceptId]);

  // THE GATE BLOCKS THE ACTION, NOT THE PAINT — and it used to block both.
  //
  // Rendering a skeleton until the check returned put a compliance call in front of every screen:
  // «تسجيل زيارة» did not begin fetching its own catalogue until the documents had been asked
  // about, and the two costs added up instead of overlapping. Measured at over a second of pure
  // waiting on a screen whose whole budget is five.
  //
  // So the children mount immediately and fetch in parallel, and the gate covers them the moment
  // it has something to say. He cannot act through it — the overlay takes the pointer — and by
  // the time it lifts, the screen underneath has already loaded.
  const blocking = outstanding !== null && outstanding.length > 0;

  if (!blocking) return <>{children}</>;

  return (
    <div className="p-4">
      <AcceptTerms
        outstanding={outstanding ?? []}
        onAccept={async (docId) => {
          if (!accept) throw new Error('accept');
          await call(session, accept, { doc_id: docId });
        }}
        // RE-READ RATHER THAN REMOVE-LOCALLY. Accepting one document can leave another outstanding
        // and the server is the only thing that knows; splicing the local array would let a person
        // through a gate that is still shut.
        onDone={() => { load().then(setOutstanding).catch(() => setOutstanding(null)); }}
        mapError={(e) => (e instanceof Error && e.message !== 'accept'
          ? 'تعذّر حفظ الموافقة. حاول مرة أخرى.'
          : 'الموافقة غير متاحة لحسابك — تواصل مع مالك الحساب.')}
      />
    </div>
  );
}
