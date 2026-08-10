// The field app consumes platform/ui AS SOURCE, exactly as its README prescribes — one alias, no
// npm package, no build step in between. platform/ is READ-ONLY: we point at it and never edit it.
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@base-ui': fileURLToPath(new URL('../../platform/ui/packages/ui/src', import.meta.url)),
    },
  },
  test: { environment: 'jsdom', globals: true, setupFiles: [] },
});
