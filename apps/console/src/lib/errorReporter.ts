/**
 * What broke in front of the person using this, sent once, to error-collector.
 *
 * THE PROBLEM IT SOLVES. Until now a screen that threw did exactly one thing: it stopped. The
 * owner saw a blank pane, called support, and support had nothing to look at — the error existed
 * for a quarter of a second inside a browser we will never see again. `POST /api/v1/signals/report`
 * turns that into a row on «سجل الأخطاء» beside the server's own, which is the whole point of the
 * two sources living in one table.
 *
 * ── THE THREE RULES, IN ORDER OF HOW BADLY BREAKING THEM WOULD HURT ─────────────────────────────
 *
 * 1. NO THROWING PATH AT ALL. This code runs INSIDE the failure handler of an application that is
 *    already failing. Every branch below is wrapped, every await is caught, and `report()` returns
 *    void rather than a promise a caller could forget to catch. A reporter that can throw turns one
 *    broken screen into an unhandled rejection, which fires the rejection handler, which calls the
 *    reporter — see rule 2.
 *
 * 2. IT MUST NOT BE ABLE TO RE-TRIGGER ITSELF. `window.onerror` and `unhandledrejection` both reach
 *    this module, and this module does a `fetch`. A failing fetch, a bad JSON body, a thrown
 *    serializer — any of them inside the handler is a loop that ends when the tab dies, having sent
 *    thousands of requests on the way. The `sending` flag below is a hard gate: while a report is
 *    in flight, another error is DROPPED rather than queued, because a queue is just a slower loop.
 *
 * 3. IT SENDS THE TOKEN THE PERSON ALREADY HAS, AND NOTHING ELSE ABOUT THEM. The route needs a
 *    session (any authenticated user may report; no capability). The tenant and the operator id
 *    ride along as CONTEXT because they are already in localStorage and they are what makes a
 *    report answerable — «which shop was this?». THE TOKEN ITSELF IS NEVER PUT IN THE BODY, and no
 *    field here is read from anywhere a page's own content could reach.
 *
 * WHY NOT AN ErrorBoundary. A boundary catches React render errors and nothing else — not an event
 * handler, not a fetch in a `useEffect`, not a rejected promise, which between them are most of what
 * actually breaks. `window.onerror` plus `unhandledrejection` is the net that catches all of it, and
 * a boundary can be added later for the SCREEN it draws, independently of the reporting done here.
 */

/** The three doors' session stores, each keyed separately on purpose (see each session.ts). */
const SHOP_KEY = 'raje3.session';
const ADMIN_KEY = 'raje3.admin.session';
const AFFILIATE_KEY = 'raje3.affiliate.session';

/** A stack is the useful part of a report and also the unbounded part. 8 KB is several dozen
 *  frames — far past where a stack stops explaining anything — and well inside the collector's own
 *  16 KB ceiling on the whole `detail` blob, so a long stack is TRUNCATED here rather than making
 *  the entire report 422 at the door and vanish. */
const MAX_STACK = 8 * 1024;

/** RULE 2, and it is a module-level flag rather than component state on purpose: there is exactly
 *  one of these per page, and it must survive every remount and every route change. */
let sending = false;
let installed = false;

/** Same origin as every other call this app makes (see src/api.ts and src/admin/api.ts, which read
 *  the same vite env). Read once, at install, so a report is not doing config lookups mid-failure. */
const BASE = ((import.meta.env?.VITE_API_BASE as string | undefined) ?? '').replace(/\/$/, '');

interface StoredSession {
  token?: string;
  access_token?: string;
  tenant?: string;
  operator?: string;
}

function readStored(key: string): StoredSession | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as StoredSession | null;
    return parsed && typeof parsed === 'object' ? parsed : null;
  } catch {
    // A private window, a disabled store, a corrupted value. Not an error worth having an opinion
    // about — it simply means there is no session to report under.
    return null;
  }
}

/** WHICHEVER DOOR THIS PERSON CAME THROUGH. The shop, the admin panel and the affiliate portal are
 *  three hostnames served by one bundle (see main.tsx), so the reporter cannot know which store to
 *  read and asks all three. The first with a token wins; there is never more than one in practice. */
function currentSession(): { token: string; tenant: string; operator: string } | null {
  for (const key of [SHOP_KEY, ADMIN_KEY, AFFILIATE_KEY]) {
    const s = readStored(key);
    const token = s?.token || s?.access_token || '';
    if (token) {
      return { token, tenant: s?.tenant ?? '', operator: s?.operator ?? '' };
    }
  }
  // SIGNED OUT MEANS NO REPORT, and that is correct rather than a gap: the route requires a
  // session, so an anonymous POST would be a 401 that this module would then have to not report.
  return null;
}

function clip(value: unknown): string {
  const s = typeof value === 'string' ? value : String(value ?? '');
  return s.length > MAX_STACK ? `${s.slice(0, MAX_STACK)}\n… (truncated)` : s;
}

/** The one-line summary a person reads in the table. Bounded, because `message` is a required
 *  field with a length limit at the collector and an over-long one would be refused entirely. */
function summarise(value: unknown): string {
  if (value instanceof Error) {
    return `${value.name}: ${value.message}`.slice(0, 2000);
  }
  const s = typeof value === 'string' ? value : String(value ?? '');
  return (s || '(unknown error)').slice(0, 2000);
}

function stackOf(value: unknown): string {
  return value instanceof Error && value.stack ? clip(value.stack) : '';
}

/**
 * Send one report. NEVER THROWS, never returns a promise, never runs twice at once.
 *
 * `kind` says which handler saw it — an `onerror` and an `unhandledrejection` for the same
 * underlying bug look identical in the message and are two different bugs to fix.
 */
export function report(error: unknown, kind: 'onerror' | 'unhandledrejection' | 'manual'): void {
  try {
    if (sending) return;                       // RULE 2. Dropped, not queued.
    const session = currentSession();
    if (!session) return;

    const stack = stackOf(error);
    const body = {
      // BOTH SET EXPLICITLY, never defaulted by the server. A row whose source the server guessed
      // is a row the screen's own filter cannot be trusted about.
      source: 'browser',
      severity: 'error',
      // The app, in the same column a pod's service name lands in. `console` IS just another value.
      service: 'console',
      message: summarise(error),
      detail: {
        kind,
        ...(stack ? { stack } : {}),
      },
      context: {
        url: typeof window !== 'undefined' ? window.location.href : '',
        user_agent: typeof navigator !== 'undefined' ? navigator.userAgent : '',
        // ALREADY IN localStorage, and what makes a report answerable. NOT the token, and NO
        // `request_id`: this console stamps no correlation header on its outgoing requests today
        // (src/api.ts sends none), so a field here would be an empty column pretending to be a
        // join key. It gains one the day the client does.
        ...(session.tenant ? { tenant: session.tenant } : {}),
        ...(session.operator ? { operator: session.operator } : {}),
      },
    };

    sending = true;
    // FIRE AND FORGET, WITH BOTH ENDS CAUGHT. `.catch` covers a rejected fetch; the `finally`
    // clears the gate whatever happened, so one failed report does not silence every later one.
    void fetch(`${BASE}/api/v1/signals/report`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${session.token}`,
      },
      body: JSON.stringify(body),
      // NOT `keepalive`: this fires mid-session, not on unload, and keepalive carries a 64 KB
      // browser-wide budget shared with anything else using it — spending it here would break a
      // beacon that actually needs to outlive the page.
    })
      .catch(() => { /* RULE 1. A report that could not be sent is a no-op, never an error. */ })
      .finally(() => { sending = false; });
  } catch {
    // RULE 1, the outer half: a failure in the reporter itself — a serializer that threw, a
    // localStorage that raised — is swallowed here rather than escaping into the handler that
    // called us, which would call us again.
    sending = false;
  }
}

/**
 * Install the two handlers, once.
 *
 * ADDITIVE, NOT REPLACING. `window.addEventListener('error', …)` rather than assigning
 * `window.onerror`: assignment silently discards whatever was there before, and this bundle runs
 * inside a design-system shell that is entitled to its own handler. Nothing here calls
 * `preventDefault`, so the browser still logs to the console exactly as it did.
 */
export function installErrorReporter(): void {
  if (installed || typeof window === 'undefined') return;
  installed = true;

  window.addEventListener('error', (event: ErrorEvent) => {
    // `event.error` is the real Error when there is one; `event.message` is all a cross-origin
    // script gives us ("Script error."), and that is still worth one row — it is the signature of a
    // failing third-party asset, which is otherwise invisible.
    report(event.error ?? event.message, 'onerror');
  });

  window.addEventListener('unhandledrejection', (event: PromiseRejectionEvent) => {
    report(event.reason, 'unhandledrejection');
  });
}

/** Test seam only. The module-level flags are exactly what make this safe in production, and
 *  exactly what makes two tests in one file interfere without a way to clear them. */
export function __resetForTests(): void {
  sending = false;
  installed = false;
}
