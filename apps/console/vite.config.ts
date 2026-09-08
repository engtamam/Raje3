// THE CONSOLE CONSUMES OUR OWN UI KIT AS SOURCE — one alias, no npm package, no build step
// between. `ui/packages/ui/src` (repo root) is OURS: a copy taken from base-services' platform/ui
// (at their v0.16.29) the day we needed to edit it ourselves rather than ask their
// team to carry our changes upstream. `platform/` stays read-only and untouched, same as every
// backend service in it — this alias is the one exception that used to point there, and does not
// any more.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { readFileSync } from 'node:fs';
import { legalDocsPlugin } from './scripts/legalDocsPlugin';

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

// THE ONE PLACE A REBRAND BELONGS, ACTUALLY WIRED. theme.config.ts's own doc comment has always
// promised that `config/product.json`'s `brand.accent` "is injected here at build time as
// __PRODUCT_ACCENT__" — but no config anywhere ever defined it, so the app silently fell back to
// theme.config.ts's OWN hardcoded gold every build, and a change to product.json did nothing. Read
// straight from the file the doc comment already points at, so the promise is finally true.
const product = JSON.parse(readFileSync(here('../../config/product.json'), 'utf8')) as
  { brand: { accent: { light: string; dark: string } } };

export default defineConfig({
  // THE CONSOLE LIVES AT /app/, AND THE BUNDLE HAS TO KNOW. Without this every asset is written as
  // /assets/… , which under /app/ resolves at the ROOT — where the landing page answers instead,
  // and the owner gets a blank screen with no error but a MIME complaint in a console he will
  // never open. Vite exposes it back as import.meta.env.BASE_URL, which is what the router reads.
  base: '/app/',
  define: {
    __PRODUCT_ACCENT__: JSON.stringify(product.brand.accent),
  },
  plugins: [react(), legalDocsPlugin()],
  resolve: {
    alias: {
      '@base-ui': here('../../ui/packages/ui/src'),

      // AND ITS PEERS, EXPLICITLY — which is not boilerplate but the consequence of the aliasing
      // decision. Node resolves a bare import relative to the importing FILE, so `clsx` inside
      // platform/ui/.../lib/cn.ts is looked for by walking up from platform/, never reaching this
      // app's node_modules. The kit's README says to "supply the peers"; on a source alias that
      // means pointing them at ours by name. Getting this wrong fails at BUILD, loudly, which is
      // the good kind — the alternative was vendoring a second copy of React into the bundle.
      clsx: here('node_modules/clsx'),
      'tailwind-merge': here('node_modules/tailwind-merge'),
      'class-variance-authority': here('node_modules/class-variance-authority'),
      'lucide-react': here('node_modules/lucide-react'),
      'react-router-dom': here('node_modules/react-router-dom'),
      react: here('node_modules/react'),
      'react-dom': here('node_modules/react-dom'),
    },
  },
  // SAME ORIGIN IN DEVELOPMENT, WHICH IS WHY THERE IS A PROXY AND NOT A BASE URL.
  //
  // The cluster's gateway allows exactly two CORS origins — the production hosts — and it is right
  // to. Pointing the app at `http://localhost:8080` instead would mean either a browser that
  // refuses every call, or widening the allow-list on a real gateway so a developer's laptop can
  // reach it. Proxying keeps the browser on one origin, so no preflight is involved at all and the
  // deployed configuration stays exactly as strict as it should be.
  //
  // `CLUSTER` is the tunnel: ssh -N -p 22 -L 127.0.0.1:8090:127.0.0.1:30080 <ssh-user>@13.53.200.173
  // (found stale — the old line named a local port-forward alias, 127.0.0.1:2224, that
  // no longer resolves; the real host is the one ops-mcp's own config.toml connects to)
  //
  // 8090 AND 127.0.0.1, BOTH DELIBERATE. VirtualBox already publishes a forward on 127.0.0.1:8080,
  // so a tunnel asking for 8080 silently lands on ::1 instead — and then which of the two answers
  // depends on how `localhost` happens to resolve that day. It resolved to the dead one, and every
  // screen in the app reported 502 from a cluster that was serving 200.
  server: {
    host: true,                   // reachable from the host's browser, not just from localhost
    proxy: {
      '/api': {
        target: process.env.CLUSTER ?? 'http://127.0.0.1:8090',
        changeOrigin: true,
      },
    },
  },
  // `e2e/` IS PLAYWRIGHT'S, AND VITEST MUST NOT OPEN IT. Both call their entry point `test`, so
  // vitest collects the browser specs, fails to construct them, and reports four failed files
  // beside the unit results — a suite that is red for a reason that has nothing to do with the
  // code, which is how a suite stops being read.
  test: { environment: 'jsdom', globals: true, include: ['src/**/*.test.ts?(x)'] },
  build: {
    rollupOptions: {
      output: {
        // ONE VENDOR CHUNK, SPLIT FROM OUR OWN CODE — not a fix for total bytes shipped (the
        // browser still fetches the same libraries once), but a fix for CACHE INVALIDATION: before
        // this, every app commit re-hashed a single 800kB+ bundle that was mostly react/react-dom/
        // react-router-dom/lucide-react, so a returning owner re-downloaded the whole console for
        // a one-line copy change. Vendor code changes only on a dependency bump, so it now keeps
        // its own hash across ordinary app releases.
        manualChunks(id) {
          if (id.includes('node_modules')) return 'vendor';
        },
      },
    },
  },
});
