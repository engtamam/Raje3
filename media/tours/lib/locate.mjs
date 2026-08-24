/**
 * One string format for "which element", used by every tour script — so a tour is data (what
 * to find and say), never code (how Playwright's API happens to spell "find a button").
 *
 * WHY A PREFIXED STRING AND NOT RAW PLAYWRIGHT CALLS INSIDE EACH TOUR SCRIPT. A tour script that
 * imports Playwright and writes `page.getByRole('button', { name: … })` itself is a script that
 * breaks the moment the recorder's own driving details change — every tour, not just the one
 * being edited. A tour script that instead writes `role=button:النص` names WHAT it wants and
 * leaves HOW to this one file. Improve the resolver — add a strategy, fix a fallback — and every
 * tour ever written benefits without being touched.
 *
 * IT MIRRORS THE APP'S OWN e2e SUITE ON PURPOSE. apps/console/e2e/*.spec.ts already proved which
 * queries actually find each control — role+name for buttons/radios, label for form fields, text
 * for prose. A tour selector language that matched a different vocabulary would need its own,
 * separate proof that it can find anything at all. This one doesn't need that: if an e2e spec can
 * find it, a tour selector using the same strategy can too.
 *
 * Formats:
 *   role=button:اسم       → page.getByRole('button', { name: 'اسم' })
 *   role=radio:اسم         → page.getByRole('radio',  { name: 'اسم' })
 *   role=heading:اسم       → page.getByRole('heading', { name: 'اسم' })
 *   role=link:اسم          → page.getByRole('link',    { name: 'اسم' })
 *   role=navigation        → page.getByRole('navigation')     (no name — the shell's own nav)
 *   label=اسم               → page.getByLabel('اسم')           (form fields — inputs, selects)
 *   text=نص                 → page.getByText('نص')
 *   testid=اسم              → page.getByTestId('اسم')          (for a control with no accessible name)
 *   css=.selector           → page.locator('.selector')       (escape hatch — last resort only)
 *
 * DEFAULT MATCHING MIRRORS PLAYWRIGHT'S OWN DEFAULT — whitespace-normalized substring, not
 * exact — because that is what apps/console/e2e/*.spec.ts already relies on throughout (e.g.
 * `getByRole('button', { name: 'إيقاف' })` matching a button whose title carries a longer
 * sentence after it). A trailing `!` on the name half asks for an EXACT match instead —
 * `role=button:إيقاف!` — for the rare control whose name is itself a prefix of another one.
 */

const STRATEGIES = {
  role: (page, rest) => {
    const sep = rest.indexOf(':');
    const kind = sep === -1 ? rest : rest.slice(0, sep);
    const name = sep === -1 ? undefined : rest.slice(sep + 1);
    if (name === undefined) return page.getByRole(kind);
    const exact = name.endsWith('!');
    const value = exact ? name.slice(0, -1) : name;
    return page.getByRole(kind, { name: value, exact });
  },
  label: (page, rest) => page.getByLabel(rest),
  text: (page, rest) => page.getByText(rest),
  testid: (page, rest) => page.getByTestId(rest),
  css: (page, rest) => page.locator(rest),
};

/**
 * Resolve a tour selector string to a live Playwright locator.
 *
 * NOT CACHED. A locator built from `role=button:إيقاف` re-queries the live DOM on every use —
 * that is Playwright's own design, and it is exactly what a tour needs: the same string that
 * found the "stop" button before an action re-finds it (or correctly fails to) after one, with
 * no stale reference to a node the page already replaced.
 */
export function locate(page, selector) {
  const sep = selector.indexOf('=');
  if (sep === -1) {
    throw new Error(`selector "${selector}" has no strategy prefix — expected role=/label=/text=/testid=/css=`);
  }
  const strategy = selector.slice(0, sep);
  const rest = selector.slice(sep + 1);
  const fn = STRATEGIES[strategy];
  if (!fn) {
    throw new Error(`unknown selector strategy "${strategy}" in "${selector}" — known: ${Object.keys(STRATEGIES).join(', ')}`);
  }
  return fn(page, rest);
}
