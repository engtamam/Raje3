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
 *
 * AND IT IS THE VERSION THE BACK END SPEAKS. This console pinned v21.0 while the onboarding
 * adapter behind it was calling Graph v26.0 — one product holding two conversations with Meta,
 * which nobody chose and nothing reported. `ci/check_the_meta_versions_are_alive.py` now refuses
 * a second answer.
 */
export const GRAPH_VERSION = import.meta.env.VITE_META_GRAPH_VERSION || 'v26.0';

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
                xfbml: false, version: GRAPH_VERSION });
      resolve('ready');
    };
    // A FAILED LOAD IS ANSWERED, NEVER LEFT HANGING. A promise that never settles leaves the
    // button spinning for ever, which is the one state that tells the owner nothing at all.
    el.onerror = () => { pending = null; resolve('failed'); };
    document.head.appendChild(el);
  });
  return pending;
}
