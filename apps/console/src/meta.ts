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
 * AND «NOT CONFIGURED» IS A DIFFERENT ANSWER FROM «FAILED TO LOAD». Without an app id there is
 * nothing to load and refreshing changes nothing; with one, a load failure is a network fault the
 * owner can retry. One sentence for both is how a person spends an afternoon on a door that was
 * never open.
 */

export type SdkState = 'unconfigured' | 'loading' | 'ready' | 'failed';

/** Meta's `FB`, in the shape this application uses and no wider. */
export interface MetaSdk {
  init: (opts: Record<string, unknown>) => void;
  login: (cb: (r: unknown) => void, opts: Record<string, unknown>) => void;
}

const SRC = 'https://connect.facebook.net/en_US/sdk.js';

/**
 * THE GRAPH VERSION IS PINNED, and pinned in configuration rather than in this file.
 *
 * `FB.init` requires it and Meta retires versions on a schedule: an unpinned default drifts under
 * us on a date somebody else chooses, and the failure would arrive as a connect flow that stopped
 * returning what our exchange expects. A default here keeps a local run working; the deployment
 * names the version it was tested against.
 */
const VERSION = import.meta.env.VITE_META_GRAPH_VERSION || 'v21.0';

/**
 * WHICH EMBEDDED SIGNUP THE POPUP OPENS — and it is READ, never decided here.
 *
 * Meta retires v2 on 15 October 2026. The successor, v4, is NOT selected by anything in this file:
 * it is decided by the Facebook Login for Business configuration behind `config_id`, and the docs
 * are explicit that «the extras object is purposely empty for v4». Earlier versions are the
 * opposite — they are told which shape to use through `extras`.
 *
 * SO THE TWO MUST AGREE, AND ONLY THE DEPLOYMENT KNOWS. The day a new configuration id is pasted
 * in, this value moves with it in the same file — one deploy, no code change, and no window in
 * which the popup is opened for one version while the console asks for another. Hardcoding either
 * half here would make the switch a release rather than a setting.
 */
const SIGNUP_VERSION = import.meta.env.VITE_META_SIGNUP_VERSION || 'v3';

/**
 * The `extras` for `FB.login`, for the version this deployment is configured against.
 *
 * `setup: {}` in both: it is where a pre-filled business profile would go, and we pre-fill nothing
 * — the owner's own details are his to type, and a wrong guess costs him a correction inside a
 * popup he cannot leave.
 */
export function signupExtras(): Record<string, unknown> {
  if (SIGNUP_VERSION === 'v4') return { setup: {} };
  // v3 and earlier: the flow needs to be told which payload shape to post back.
  return { setup: {}, featureType: '', sessionInfoVersion: '3' };
}

let pending: Promise<SdkState> | null = null;

export function metaSdk(): MetaSdk | null {
  return (window as unknown as { FB?: MetaSdk }).FB ?? null;
}

/** Load and initialise the SDK once. Repeated calls share the first attempt. */
export function loadMetaSdk(): Promise<SdkState> {
  if (!import.meta.env.VITE_META_APP_ID) return Promise.resolve<SdkState>('unconfigured');
  if (metaSdk()) return Promise.resolve<SdkState>('ready');
  if (pending) return pending;

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
      fb.init({ appId: import.meta.env.VITE_META_APP_ID, cookie: false,
                xfbml: false, version: VERSION });
      resolve('ready');
    };
    // A FAILED LOAD IS ANSWERED, NEVER LEFT HANGING. A promise that never settles leaves the
    // button spinning for ever, which is the one state that tells the owner nothing at all.
    el.onerror = () => { pending = null; resolve('failed'); };
    document.head.appendChild(el);
  });
  return pending;
}
