// The console consumes platform/ui AS SOURCE — one alias, no npm package, no build step between.
// platform/ is READ-ONLY: we point at it and never edit it, which is what lets their releases
// arrive on their own (v0.16.0 shipped four auth screens we did not have to write).
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

const here = (p: string) => fileURLToPath(new URL(p, import.meta.url));

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@base-ui': here('../../platform/ui/packages/ui/src'),

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
  test: { environment: 'jsdom', globals: true },
});
