/**
 * The number pad — the one part of this screen the operator uses without looking at it.
 *
 * A calculator layout, and deliberately not a phone's `<input type="tel">`. The system keyboard on
 * a tablet covers half the screen, appears and disappears under his hand, and puts the digits
 * somewhere different on every device. The whole grid must stay visible while he types, because
 * the matches appear beside it as he goes.
 *
 * WESTERN DIGITS, ALWAYS — 0-9, and never the Arabic-Indic forms. Saudi phone numbers are written
 * and read in Western digits everywhere they matter, and a pad that rendered the other set would
 * produce a number that looks right to the operator and matches nothing in the store.
 *
 * (This file cannot show you the forms it rejects: the build refuses any of them anywhere in our
 * source, comments included, which is exactly the guard being described.)
 */
import { useCallback } from 'react';

/** The keys, in calculator order — 7 8 9 on top, 0 at the bottom. Not a phone's 1 2 3 first: the
 *  people using this have used a calculator every day of their working lives. */
const KEYS = ['7', '8', '9', '4', '5', '6', '1', '2', '3'];

export interface KeypadProps {
  value: string;
  onChange: (next: string) => void;
  /** How long a number may get. Configuration rather than a constant here: 05xxxxxxxx is ten
   *  digits and 9665xxxxxxxx is twelve, and a shop near a border serves both. */
  maxLength?: number;
  disabled?: boolean;
}

export function Keypad({ value, onChange, maxLength = 15, disabled = false }: KeypadProps) {
  const press = useCallback((d: string) => {
    if (disabled || value.length >= maxLength) return;
    onChange(value + d);
  }, [disabled, maxLength, onChange, value]);

  const back = useCallback(() => {
    if (disabled) return;
    onChange(value.slice(0, -1));
  }, [disabled, onChange, value]);

  return (
    /* KEYS THAT SHRINK WITH THE VIEWPORT, NOT ROWS THAT SHARE IT.
       I tried `h-full` + `grid-rows-4` so four rows would divide whatever height was left. It
       collapsed: `.touch-only` sets `display: block`, which kills the flex column above it, so the
       rows resolved to zero and the digits stacked on top of each other. A percentage height needs
       a definite parent, and that chain had a block in the middle of it.
       So the keys are sized directly instead — smaller on a short screen, h-16 from `sm` up. It is
       plain, it cannot collapse, and a greasy finger still gets a 56px target at the worst. */
    <div className="grid grid-cols-3 gap-2" role="group" aria-label="لوحة الأرقام">
      {KEYS.map((d) => (
        <Key key={d} label={d} onPress={() => press(d)} disabled={disabled} />
      ))}
      {/* CLEAR IS NOT WHERE A MISTAKE LANDS. It sits in the corner away from the digits, because
          the cost of hitting it by accident is the whole number retyped with a customer waiting,
          while the cost of a slightly longer reach is nothing. */}
      <Key label="مسح" onPress={() => onChange('')} disabled={disabled || !value} muted />
      <Key label="0" onPress={() => press('0')} disabled={disabled} />
      <Key label="⌫" onPress={back} disabled={disabled || !value} muted />
    </div>
  );
}

function Key({ label, onPress, disabled, muted }: {
  label: string; onPress: () => void; disabled?: boolean; muted?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onPress}
      disabled={disabled}
      // h-16 IS THE SPECIFICATION, NOT A PREFERENCE. A finger with workshop grease on it is not a
      // mouse pointer; a key smaller than a thumb is a mistyped number, and a mistyped number is a
      // reminder sent to a stranger.
      className={[
        'h-14 rounded-xl text-2xl font-semibold tabular-nums transition-transform sm:h-16',
        'active:scale-95 disabled:opacity-40',
        muted
          ? 'bg-surface-2 text-text-secondary'
          : 'bg-surface-1 text-text-primary shadow-sm',
      ].join(' ')}
    >
      {label}
    </button>
  );
}
