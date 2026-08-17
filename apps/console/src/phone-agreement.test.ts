/**
 * The field screen must not refuse a customer the service would record.
 *
 * The phone rule and the plate rule sat three lines apart in `Visit.tsx` under opposite doctrines:
 * the plate comment said we do not enforce a national format because a refusal the operator cannot
 * satisfy becomes «1» typed into the box — and the phone line enforced exactly that, against a
 * service whose own code says an unusual number «is stored as typed rather than refused».
 *
 * `fixtures/phones.json` is the list; `services/operations/tests/unit/test_phone_agreement.py`
 * reads the same rows.
 */
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import { describe, expect, it } from 'vitest';

import { digitsOnly, western } from './digits';

const CORPUS = JSON.parse(
  readFileSync(join(process.cwd(), '..', '..', 'fixtures', 'phones.json'), 'utf8'),
) as { cases: { phone: string; accepted: boolean; saudiMobile: boolean; note: string }[] };

/** What the save button asks — `phoneUsable` in Visit.tsx, mirroring the service. */
function screenAccepts(typed: string): boolean {
  return western(typed).trim().length >= 3;
}

/** What the hint asks — `phoneOk`: can a reminder actually reach him. */
function reachable(typed: string): boolean {
  return /^05\d{8}$/.test(digitsOnly(typed));
}

describe('the field screen records whoever the service would record', () => {
  it('has a corpus to agree on', () => {
    expect(CORPUS.cases.length).toBeGreaterThan(4);
  });

  for (const c of CORPUS.cases) {
    it(`${c.accepted ? 'records' : 'refuses'} ${JSON.stringify(c.phone)} — ${c.note}`, () => {
      expect(screenAccepts(c.phone)).toBe(c.accepted);
    });

    it(`says reminders ${c.saudiMobile ? 'reach' : 'do NOT reach'} ${JSON.stringify(c.phone)}`, () => {
      expect(reachable(c.phone)).toBe(c.saudiMobile);
    });
  }
});
