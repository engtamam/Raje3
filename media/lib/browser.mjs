/**
 * Where the browser comes from — shared by every recorder.
 *
 * Playwright is installed with the console app, not at the repo root: it is that app's testing
 * tool, and it belongs to it. Resolving it explicitly from apps/console/package.json means every
 * recorder always launches the exact same browser build the e2e suite already exercises — never
 * a second copy installed just for recording that quietly drifts out of step with it.
 */
import { createRequire } from 'node:module';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = dirname(fileURLToPath(import.meta.url));
const CONSOLE_PKG = resolve(HERE, '../../apps/console/package.json');

export function chromiumModule() {
  const req = createRequire(CONSOLE_PKG);
  return req('@playwright/test').chromium;
}
