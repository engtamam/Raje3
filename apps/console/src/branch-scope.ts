/**
 * Which branch the whole console is currently looking at — one choice, every screen.
 *
 * WHERE IT WAS. A branch switcher existed, in the header of «محلّي», and nowhere else. So the
 * numbers on one screen could be about Jeddah while the customer list beside it was about the
 * whole chain, and nothing on either screen said so. An owner comparing «عملائي» against a
 * «محلّي» he had narrowed was comparing two different shops and had no way to notice.
 *
 * THE RULE THAT DECIDES EVERYTHING HERE — «يُضيِّق ولا يوسّع أبداً». The choice can only ever
 * remove data from a view. It is built from the branches the SERVER handed this person, which are
 * already narrowed to what they may read (`api/v1/staff.py`, §12.4) — never from a list this
 * module assembles. A person granted one branch is offered no switcher at all, because a control
 * that filters by your only branch is a question you have to stop and answer for nothing.
 *
 * AND THE SERVER IS THE ONE THAT ENFORCES IT. Everything in this file is a convenience: forge the
 * stored value, and the reads still come back narrowed, because `branch_scope` resolves from the
 * token and not from anything the browser sends. That is what makes it safe to keep this choice
 * in localStorage at all.
 *
 * EMPTY MEANS EVERYTHING — the same convention the server uses, so no layer has to translate.
 */

/** One entry in the switcher: what the server said this person may see. */
export interface ScopeBranch { id: string; name?: string }

export const KEY = 'raje3.branch';

/**
 * The stored choice, made safe against what may have happened since it was stored.
 *
 * A CHOICE OUTLIVES THE PERMISSION THAT ALLOWED IT, and that is the whole reason this function
 * exists rather than a bare `localStorage.getItem`. An owner narrows the console to Jeddah on
 * Tuesday; on Wednesday his own scope changes, or the branch is closed and removed from his list.
 * The stored id is then a branch he may not read — and a console that kept asking for it would
 * show him empty screens for as long as he did not think to look at the switcher.
 *
 * So the stored value is only honoured while it is still ON the list the server just sent. When it
 * is not, we fall back to «everything», which is the state a person understands without being
 * told: he sees his whole scope, which is never more than he is allowed.
 */
export function currentBranch(allowed: ScopeBranch[], stored: string | null): string {
  const id = (stored ?? '').trim();
  if (!id) return '';
  return allowed.some((b) => b.id === id) ? id : '';
}

/**
 * Whether to render the control at all.
 *
 * ONE BRANCH IS NO CHOICE. Rendering it would ask a single-branch shop — and every manager scoped
 * to one place — to think about a filter that cannot change anything. Two is the first number at
 * which the control means something.
 */
export function canSwitch(allowed: ScopeBranch[]): boolean {
  return allowed.length > 1;
}

/** Read the stored choice. Never throws: a browser with storage disabled is a working console. */
export function loadBranch(): string {
  try {
    return window.localStorage.getItem(KEY) ?? '';
  } catch {
    return '';
  }
}

/**
 * Remember it across sessions — «الفرع المختار يبقى بين الجلسات».
 *
 * A MANAGER OF ONE BRANCH OPENS THIS PRODUCT EVERY MORNING. Asking him to re-narrow it daily is
 * asking him to do the same small thing three hundred times a year, and the day he forgets he
 * reads the chain's numbers as his own.
 */
export function saveBranch(id: string): void {
  try {
    if (id) window.localStorage.setItem(KEY, id);
    else window.localStorage.removeItem(KEY);
  } catch {
    // A browser that refuses storage still gets a working console for this session. The choice
    // simply does not survive the tab, which is a smaller failure than a screen that will not load.
  }
}

/**
 * The query a screen sends. One shape, so no screen invents its own spelling of the same idea.
 *
 * «كل الفروع» SENDS NOTHING AT ALL rather than an empty string, because an empty `branch_id=` in
 * a query is a value the server would have to decide the meaning of — and the two readings, «the
 * whole shop» and «the branch whose id is empty», are not the same question.
 */
export function scopeQuery(branch: string): Record<string, string> {
  return branch ? { branch_id: branch } : {};
}

/**
 * How many visits the current view is NOT showing — the honest line under the switcher (§10.6.4).
 *
 * A BRANCH SCOPE RENDERS EXACTLY LIKE THE WHOLE SHOP: same cards, same ring, same words. Without
 * this number an owner who forgets which scope he is in reads one branch's return rate as his
 * business's. The unspecified visits are counted here too, because they are outside EVERY branch
 * view rather than merely outside this one.
 *
 * IT LIVES BESIDE THE CONTROL NOW, not inside «محلّي». The switcher moved to the rail and became a
 * choice about every screen; a sentence explaining that choice, left behind on one screen, would
 * be absent from the three screens it also describes.
 *
 * Zero on «كل الفروع», where nothing is outside the view and the sentence would be noise.
 */
export function outsideVisits(
  rows: { branch_id?: string; visits?: number }[], unknown: number, branch: string,
): number {
  if (!branch) return 0;
  const total = rows.reduce((n, r) => n + (r.visits ?? 0), 0) + unknown;
  const here = rows.find((r) => r.branch_id === branch)?.visits ?? 0;
  return Math.max(0, total - here);
}
