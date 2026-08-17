/**
 * «متى نرسل» listed thirteen sentences and said nothing about what any of them IS.
 *
 * THE DEFECT, AS AN OWNER MET IT. The rows read as one flat list — «سُجّلت زيارة»، «حان وقت
 * الخدمة»، «تجاوز دورته ولم يعد» — and nothing distinguished the promotional ones from the
 * service ones. Those two behave nothing alike: a promotional message may not go out without the
 * customer's explicit consent, may not be sent between 10pm and 7am, counts against a different
 * cap, and is billed by Meta at the higher rate. The owner carries the fine for all four.
 *
 * And because the promotional rows were indistinguishable, the list also read as SHORTER than it
 * is — the first reading of the screen was «عدد الرسائل قليل», about a list that held every
 * automatic reason the product has.
 *
 * Source-shape assertions rather than rendered DOM, for the reason gates.test.ts gives: what is
 * pinned is that the branch exists and is fed by the right field. The Arabic itself comes from
 * the server (`reasons.CLASS_LABEL`), so a test asserting the words here would be asserting a
 * copy of them.
 */
import { describe, expect, it } from 'vitest';

import messagesSrc from './screens/Messages.tsx?raw';

describe('the class of every reason reaches the screen', () => {
  it('the row carries a badge fed by the server, not by a guess', () => {
    // BOTH FIELDS. `cls` is what the colour is chosen by and `cls_label` is what is printed —
    // a screen that received only the key would have to invent the Arabic, and an invented name
    // drifts from the thing it names the first time a class is renamed.
    expect(messagesSrc).toContain('cls_label');
    expect(messagesSrc).toMatch(/Badge tone=\{CLASS_TONE\[/);
  });

  it('every one of the five classes has a tone, so none falls through unlabelled', () => {
    for (const cls of ['service', 'personal', 'awareness', 'warning', 'marketing']) {
      expect(messagesSrc).toMatch(new RegExp(`${cls}:\\s*'`));
    }
  });

  it('marketing does not wear the same quiet tone as the rest', () => {
    // IT IS THE ONE THAT COSTS HIM. Consent, the quiet window, the higher rate — all four turn on
    // this class alone, so it is the one an owner must find without reading every row.
    const tone = messagesSrc.match(/marketing:\s*'([a-z]+)'/)?.[1];
    const personal = messagesSrc.match(/personal:\s*'([a-z]+)'/)?.[1];
    expect(tone).toBeTruthy();
    expect(tone).not.toBe(personal);
  });

  it('the list says how many of each, and where the campaigns are', () => {
    // «عدد الرسائل قليل» was a reading of a flat list, not a fact about it. The count answers it,
    // and the sentence answers the question the count raises next.
    expect(messagesSrc).toContain('سبباً يرسل باسم محلّك');
    expect(messagesSrc).toContain('حملاتي');
  });
});
