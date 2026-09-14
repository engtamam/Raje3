/**
 * nav-i18n.ts — the rail's own strings, real regression coverage for the 2026-09-14 finding: the
 * sidebar never translated at all, in any language, because its labels lived as literal Arabic in
 * nav.ts/App.tsx rather than routed through operator-i18n. This file checks the two things that
 * actually matter for that class of bug never recurring: every SECTIONS id has a `nav.<id>` key,
 * and every locale answers every one of them (not just ar/en).
 */
import { describe, expect, it } from 'vitest';
import { SECTIONS } from './nav';
import { OPERATOR_LOCALES, translate } from './operator-i18n';
import './nav-i18n';

const SHELL_KEYS = ['shell.collapse', 'shell.expand', 'shell.signOut', 'shell.account'];

describe('nav-i18n — every section and every shell control, in every locale', () => {
  for (const locale of OPERATOR_LOCALES.map((l) => l.value)) {
    it(`${locale}: every SECTIONS id has its own nav.<id> key, not the raw key echoed back`, () => {
      for (const s of SECTIONS) {
        const key = `nav.${s.id}`;
        expect(translate(locale, key)).not.toBe(key);
      }
    });

    it(`${locale}: every shell chrome label is translated`, () => {
      for (const key of SHELL_KEYS) {
        expect(translate(locale, key)).not.toBe(key);
      }
    });
  }

  it('nav.unavailableSuffix actually substitutes the label placeholder', () => {
    const filled = translate('en', 'nav.unavailableSuffix').replace('{label}', 'Campaigns');
    expect(filled).toContain('Campaigns');
    expect(filled).not.toContain('{label}');
  });
});
