/**
 * The screen must not turn away a plate the service accepts.
 *
 * These two decisions were written separately and drifted: `operations/core/plate.py` took an
 * Arabic-lettered plate and this screen refused it — the operator typed what is stamped on the car
 * and the save button stayed dark, with nothing to read, because a disabled button cannot explain
 * itself. `fixtures/plates.json` is now the single list, and its twin in
 * `services/operations/tests/unit/test_plate_agreement.py` asserts the same rows.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { formatPlate } from './screens/Visit';

// Read from the repository root rather than a URL: vitest runs with `apps/console` as its cwd,
// and the point of this file is that the list lives in ONE place both languages can reach.
const CORPUS = JSON.parse(
  readFileSync(join(process.cwd(), '..', '..', 'fixtures', 'plates.json'), 'utf8'),
) as { cases: { plate: string; accepted: boolean; note: string }[] };

/** What the screen decides — `formatPlate` on every keystroke, then the `plateOk` rule. */
function screenAccepts(raw: string): boolean {
  const shown = formatPlate(raw);
  // arabic-indic-digits: intentional — this mirrors the guard in Visit.tsx exactly.
  return /[0-9٠-٩]/.test(shown) && /\p{L}/u.test(shown);
}

describe('the screen agrees with the service about what a plate is', () => {
  it('has a corpus to agree on', () => {
    expect(CORPUS.cases.length).toBeGreaterThan(4);
  });

  for (const c of CORPUS.cases) {
    it(`${c.accepted ? 'accepts' : 'refuses'} ${JSON.stringify(c.plate)} — ${c.note}`, () => {
      expect(screenAccepts(c.plate)).toBe(c.accepted);
    });
  }
});
