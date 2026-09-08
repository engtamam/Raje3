/**
 * Meta's JavaScript SDK — loaded here, once, or honestly declared missing.
 *
 * THE HOLE THIS CLOSES, AND IT CLOSED THE PRODUCT'S FRONT DOOR. `Connect.tsx` read `window.FB`
 * and nothing in this application ever put it there: no script tag in index.html, no loader, no
 * `FB.init`. So «اربط واتساب» took its `if (!fb)` branch on every press since the day it was
 * written, and the sentence it showed — «حدّث الصفحة وحاول مرة أخرى» — sent the owner to refresh
 * a page that would fail again identically. Connecting WhatsApp is the one thing this product
 * cannot work without, and it was unreachable from the screen that offers it.
 *
 * LOADED WHEN THE PANE OPENS, NOT IN index.html. A tag in the page head puts a request to Meta on
 * the critical path of every screen — the field screen, the till, the customer list — for a button
 * almost nobody presses twice in a shop's lifetime. The pane that needs it asks for it.
 *
 * NOT A BUILD-TIME SECRET, A RUNTIME READ. The App ID and Facebook Login Config ID used to be
 * baked in at Docker build time (`VITE_META_APP_ID`/`VITE_META_CONFIG_ID`) — meaning setting them
 * meant a console rebuild, not a form. Neither is actually secret (both travel from THIS browser
 * to Meta's own JS SDK in the clear on every popup open already), so `Connect.tsx` now fetches
 * them from `GET /api/v1/whatsapp/config` — the same operator-set value the admin's «المزوّدين
 * الخارجيين» panel writes — and hands them to `loadMetaSdk` below. Nothing here reads
 * `import.meta.env` for a Meta value any more.
 *
 * AND «NOT CONFIGURED» IS A DIFFERENT ANSWER FROM «FAILED TO LOAD». Without an app id there is
 * nothing to load and refreshing changes nothing; with one, a load failure is a network fault the
 * owner can retry. A config fetch that itself fails (network error, session expired) collapses
 * into the SAME `'unconfigured'` state — ours, never his, and the honest sentence the console
 * already shows for it — rather than inventing a fourth, less legible state.
 */

export type SdkState = 'unconfigured' | 'loading' | 'ready' | 'failed';

/** Meta's `FB`, in the shape this application uses and no wider. */
export interface MetaSdk {
  init: (opts: Record<string, unknown>) => void;
  login: (cb: (r: unknown) => void, opts: Record<string, unknown>) => void;
}

/** What `GET /api/v1/whatsapp/config` answers — see connect.py's own docstring on why none of
 *  this is secret despite riding the sealed-secrets panel for admin-UX reasons alone. */
export interface MetaConfig {
  app_id: string;
  config_id: string;
  graph_version: string;
  configured: boolean;
}

const SRC = 'https://connect.facebook.net/en_US/sdk.js';

/**
 * THE GRAPH VERSION'S OWN FALLBACK — a defensive default, kept even though the real value now
 * travels with `MetaConfig.graph_version`. A backend that answers `configured: true` with an
 * empty `graph_version` (a config gap on our side, not the owner's) must still never call
 * `FB.init` with an undefined version; this is that safety net, never the source of truth.
 * `ci/check_the_meta_versions_are_alive.py` pins the REAL value against the backend's own
 * settings default now, not against a string in this file.
 */
export const GRAPH_VERSION_FALLBACK = 'v26.0';

/**
 * The `extras` for `FB.login`, and it is EMPTY — that is Embedded Signup v4's whole shape.
 *
 * WHICH VERSION THE POPUP OPENS IS NOT DECIDED HERE, and cannot be. It is a property of the
 * Facebook Login for Business configuration behind `config_id`, set on Meta's side; v4 reads it
 * from there and takes no parameters. Earlier versions were the opposite — they were told through
 * `extras` which payload shape to post back, with `featureType` and `sessionInfoVersion`.
 *
 * THOSE TWO KEYS ARE GONE FROM THIS FILE RATHER THAN KEPT BEHIND A SWITCH. v2 and v3 both retire
 * on 15 October 2026, so a branch serving them is not compatibility — it is a path to a date. And
 * there is nothing behind it: no shop has ever completed this flow, because the Meta application
 * itself is not created yet.
 *
 * `setup` is where a pre-filled business profile would go, and we pre-fill nothing — the owner's
 * own details are his to type, and a wrong guess costs him a correction inside a popup he cannot
 * leave.
 */
export const SIGNUP_EXTRAS: Record<string, unknown> = {};

let pending: Promise<SdkState> | null = null;

export function metaSdk(): MetaSdk | null {
  return (window as unknown as { FB?: MetaSdk }).FB ?? null;
}

/** Load and initialise the SDK once, against a config fetched from the backend. Repeated calls
 *  (with any config) share the first attempt — the same one-popup-pane assumption `Connect.tsx`
 *  already makes, since Meta's own SDK is a single global regardless of which card asked. */
export function loadMetaSdk(config: MetaConfig | null): Promise<SdkState> {
  if (!config || !config.configured || !config.app_id) return Promise.resolve<SdkState>('unconfigured');
  if (metaSdk()) return Promise.resolve<SdkState>('ready');
  if (pending) return pending;

  const version = config.graph_version || GRAPH_VERSION_FALLBACK;
  pending = new Promise<SdkState>((resolve) => {
    const el = document.createElement('script');
    el.src = SRC;
    el.async = true;
    el.crossOrigin = 'anonymous';
    el.onload = () => {
      const fb = metaSdk();
      if (!fb) { resolve('failed'); return; }
      // `cookie: false` — we take nothing from Meta but the message the popup posts back, and a
      // session cookie set on our origin is a thing to secure for no benefit.
      fb.init({ appId: config.app_id, cookie: false, xfbml: false, version });
      resolve('ready');
    };
    // A FAILED LOAD IS ANSWERED, NEVER LEFT HANGING. A promise that never settles leaves the
    // button spinning for ever, which is the one state that tells the owner nothing at all.
    el.onerror = () => { pending = null; resolve('failed'); };
    document.head.appendChild(el);
  });
  return pending;
}
