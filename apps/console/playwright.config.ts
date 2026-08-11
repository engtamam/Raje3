/**
 * The end-to-end pass — against the REAL cluster, in a real browser.
 *
 * NOT A MOCK, and that is the whole value. Every unit test in this repo passes against fakes we
 * wrote; the failures that actually cost days were a route the manifest declared and the app never
 * served, a capability the console assumed and the token did not carry, and a pod running old code
 * under a correct-looking digest. None of those is visible to a mocked test — all three are
 * visible the moment a browser asks the cluster a question.
 *
 * REACHABILITY IS PART OF THE SETUP, NOT A PRECONDITION SOMEBODY REMEMBERS. The dev server proxies
 * /api to the tunnel (see vite.config.ts), so the browser stays on one origin and the production
 * CORS list is not widened for a laptop. Open the tunnel first:
 *
 *   ssh -N -p 2224 -L 127.0.0.1:8090:127.0.0.1:30080 tamam@127.0.0.1
 *
 * ONE WORKER, and it is not about speed. The pass opens a shop and then works inside it; two
 * running at once would be two shops racing through the same phone-number space, and the failure
 * would read as a flaky test rather than as the collision it is.
 */
import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  workers: 1,
  // WHICH FILES RUN — not the order they run in, and the difference was worth learning. Playwright
  // sorts by path regardless of this list, so `customers` runs before `door` no matter how the
  // array reads; a comment here once claimed otherwise and the run disproved it on the first try.
  //
  // Which is fine, because the ORDER IS NOT LOAD-BEARING. The `shop` fixture opens a shop when it
  // lands on the door — it has to anyway, since a token lives an hour and a suite run after lunch
  // starts signed out. Whichever file runs first pays for the signup and the rest inherit it.
  //
  // A new page spec is still added to this list. That is deliberate friction: a file that runs
  // without anybody deciding it belongs is a file whose failures nobody can place.
  testMatch: [
    'door.spec.ts',
    'today.spec.ts',
    'visit.spec.ts',
    'customers.spec.ts',
    'shop.spec.ts',
    'services.spec.ts',
    'messages.spec.ts',
    'points.spec.ts',
    'team.spec.ts',
    'account.spec.ts',
    'roles.spec.ts',
  ],
  // Generous, because these are real network calls to a real cluster over an SSH tunnel — not
  // because anything here is slow by design. A tight timeout on a live pass produces failures
  // that say nothing about the product.
  timeout: 60_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.CONSOLE ?? 'http://localhost:5174',
    locale: 'ar-SA',
    // The screenshot is the artefact worth having when a live pass fails: the sentence the owner
    // would have read is on it, and no log line carries that.
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  // ITS OWN SERVER, ON ITS OWN PORT, NEVER THE ONE A PERSON IS USING. This reused whatever was
  // already on 5173 — which is where the dev server a developer is browsing lives. Restarting that
  // server mid-run took the whole suite down with ERR_CONNECTION_REFUSED, and twelve specs failed
  // for a reason that had nothing to do with the product. A suite whose result depends on what
  // somebody else was doing at the time is a suite nobody trusts.
  webServer: {
    command: 'npx vite --port 5174 --strictPort',
    url: 'http://localhost:5174',
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
