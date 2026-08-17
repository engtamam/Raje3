/**
 * The keyboard half of the same defect the services carry (see each service core digits.py).
 *
 * These are not about a wrong value arriving. They are about the box not responding at all: the
 * character is deleted between the key and the state, so the operator sees an empty field, has no
 * error to read, and nothing to correct.
 */
import { describe, expect, it } from 'vitest';

import { digitsOnly, western } from './digits';
import { formatPlate } from './screens/Visit';

describe('a digit typed on an arabic keyboard reaches the box', () => {
  it('folds both scripts rather than deleting them', () => {
    // arabic-indic-digits: intentional — this is the input the defect came from.
    expect(western('٠٥٠١٢٣٤٥٦٧')).toBe('0501234567');
    expect(western('۰۵۰۱۲۳۴۵۶۷')).toBe('0501234567');
    expect(digitsOnly('٥ ٤٣')).toBe('543');
  });

  it('keeps a four-digit PIN he can actually type', () => {
    // WhoIsSaving and Team both do `digitsOnly(...).slice(0, 4)`. Before this, `/\D/g` deleted
    // every one of these and the field stayed empty while he typed.
    expect(digitsOnly('١٢٣٤').slice(0, 4)).toBe('1234');
  });

  it('lets a plate typed in arabic survive the formatter that runs on every keystroke', () => {
    // The premise: `plateOk` accepts /[0-9٠-٩]/ deliberately, and could never see one because
    // `formatPlate` had already stripped it. This returned '' before the fix.
    expect(formatPlate('ABC ٤٥٦')).toBe('456 ABC');
    expect(formatPlate('٤٥٦')).toBe('456');
  });
  it("takes the customer's phone as the operator typed it", () => {
    // THE ONE MY FIRST SWEEP MISSED. I grepped for `[0-9]` and `inputMode` and found six inputs;
    // this one spells the filter `/\D/g`, so it was invisible to that search and turned up only
    // when the gate swept for the idiom itself. It is the field screen's phone box — the value the
    // whole product hangs on, since recognising the returning customer starts here.
    expect(digitsOnly('٠٥٠١٢٣٤٥٦٧').slice(0, 10)).toBe('0501234567');
  });
});
