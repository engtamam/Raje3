/**
 * A `wa.me` link, built the same way `phone.ts`'s own `asLocal` reasons about the two phone forms
 * — except this boundary runs the other direction: `wa.me` wants E.164 digits with no `+`, and a
 * lead's own `phone` field can arrive as either `05…` or `966…` depending on where it was sourced
 * (Google Places vs. typed in by a promoter). Normalizing here, once, is what lets every call site
 * just hand over whatever `lead.phone` happens to hold.
 *
 * `text`, WHEN GIVEN, PRE-FILLS WHATSAPP'S OWN COMPOSER — it does not send anything by itself; the
 * person still taps WhatsApp's own send button. That is exactly the fast-path this exists for: one
 * tap from a template to an editable, ready-to-send message, instead of a copy/switch-app/paste
 * round trip.
 */
import { digitsOnly } from '../digits';

/** `05xxxxxxxx` / `966xxxxxxxx` / `5xxxxxxxx` → `966xxxxxxxx`. `null` for anything that is not
 *  recognisably a Saudi mobile number — a `wa.me` link built from a mangled number opens WhatsApp
 *  to nowhere, which is worse than not offering the button at all. */
export function waDigits(phone: string): string | null {
  const d = digitsOnly(phone || '');
  if (d.startsWith('966') && d.length === 12) return d;
  if (d.startsWith('05') && d.length === 10) return `966${d.slice(1)}`;
  if (d.startsWith('5') && d.length === 9) return `966${d}`;
  return null;
}

export function waLink(phone: string, text = ''): string | null {
  const digits = waDigits(phone);
  if (!digits) return null;
  const q = text ? `?text=${encodeURIComponent(text)}` : '';
  return `https://wa.me/${digits}${q}`;
}
