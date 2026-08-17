import { digitsOnly } from './digits';/**
 * The number in the form a person reads and types.
 *
 * TWO FORMS EXIST AND ONLY ONE IS FOR HUMANS. Storage, the search index and every service speak
 * E.164 — `966501234567` — because that is the form a message is sent to. The operator, the
 * validator and every screen speak the local form, `0501234567`, because that is what is written
 * on a card, said aloud, and typed into a keypad.
 *
 * CONVERTING AT THE ONE BOUNDARY WHERE A STORED NUMBER ENTERS A SCREEN is what keeps the rest of
 * the app from having to know there are two. It lived inside the visit screen, which is where it
 * was first needed — and so «عملائي» printed `966599207587` at the top of a list an owner reads
 * fifty times a day, and «اليوم» did the same. Neither was wrong enough to report and both were
 * wrong enough to slow a person down every time.
 */
export function asLocal(phone: string): string {
  const d = digitsOnly(phone || '');
  if (d.startsWith('966')) return `0${d.slice(3)}`;
  if (d.startsWith('05')) return d;
  // ANYTHING ELSE IS RETURNED AS IT CAME. A number we cannot recognise is not ours to rewrite —
  // stripping its punctuation would turn an oddity into a plausible-looking wrong number.
  return phone;
}
