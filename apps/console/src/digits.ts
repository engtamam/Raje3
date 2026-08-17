/**
 * Arabic-Indic digits folded to Western ones, before any box decides what he typed.
 *
 * WHAT THE SCREENS WERE DOING, AND IT IS WORSE THAN A WRONG VALUE. Six inputs filtered the typed
 * string with `/\D/g` or `/[^0-9]/g`. In JavaScript both mean exactly `0-9`, so a keyboard set to
 * Arabic produced characters that were DELETED on the way into the box. He types his four-digit
 * PIN and the field stays empty. There is no error to read, nothing to correct, and no reason
 * offered — the screen simply does not respond to his typing.
 *
 * WHERE IT LANDS HARDEST. `WhoIsSaving` is the PIN prompt on the field screen, entered with a
 * customer standing in front of him, dozens of times a day. `Team` is where an owner sets that PIN
 * in the first place — so a shop could be locked out of a code it never successfully typed.
 *
 * AND ONE SCREEN CONTRADICTED ITSELF IN TWO LINES. `Visit.tsx` guards the plate with
 * `/[0-9٠-٩]/`, under a comment stating plainly that a plate is typed on an Arabic keyboard as
 * often as a Latin one and that refusing those digits would refuse a correct plate. Two hundred
 * lines above, `formatPlate` — which runs on EVERY KEYSTROKE — stripped them. The guard could
 * never see the character it was written to accept: `formatPlate('ا ب ج ٤٥٦')` returned the empty
 * string. The defence was dead, and the operator was blocked by the very screen that meant to let
 * him through.
 *
 * THIS MIRRORS EACH SERVICE’S OWN `app/core/digits.py` DELIBERATELY, down to the two ranges. The server
 * folds what reaches it; this folds what reaches the server. Neither is redundant: the server
 * cannot fix a character the browser already deleted, and the browser cannot be the only guard for
 * a till that posts straight to the API.
 */

// arabic-indic-digits: intentional — this module converts them to 0-9, so it must name them.
// ٠١٢٣٤٥٦٧٨٩ and the Eastern-Arabic (Persian/Urdu) ۰۱۲۳۴۵۶۷۸۹, because a phone sold in this
// market ships either keyboard and the person typing cannot tell you which one their thumb used.
const FOLD: Record<string, string> = {
  '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4',
  '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9',
  '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4',
  '۵': '5', '۶': '6', '۷': '7', '۸': '8', '۹': '9',
};

/** The same string with every Arabic-Indic or Eastern-Arabic digit in Western form. */
export function western(text: string): string {
  return (text ?? '').replace(/[٠-٩۰-۹]/g, (ch) => FOLD[ch] ?? ch);
}

/** What «a digit» means everywhere in this product: exactly these ten characters. */
const WESTERN = '0123456789';

/**
 * Fold, then keep only 0-9 — the shape every numeric box on these screens actually wants.
 *
 * WRITTEN AS A MEMBERSHIP TEST RATHER THAN `/[^0-9]/`, so that the gate banning that idiom
 * (`ci/check_a_screen_does_not_delete_what_he_typed.py`) needs no exception for the one file
 * allowed to use it. A rule with a single carve-out is a rule somebody extends to two.
 */
export function digitsOnly(text: string): string {
  return Array.from(western(text)).filter((ch) => WESTERN.includes(ch)).join('');
}
