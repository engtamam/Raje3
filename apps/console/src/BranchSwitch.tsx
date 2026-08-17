/**
 * The branch this console is looking at, chosen once at the top of the rail.
 *
 * IT USED TO LIVE IN THE HEADER OF «محلّي», and only there. So «عملائي» beside it was always the
 * whole chain while «محلّي» might be one branch, and nothing on either screen said which. An owner
 * who narrowed one screen and then read another was comparing two different shops.
 *
 * ABOVE THE NAV, WHICH IS WHERE A SCOPE BELONGS. The shell keeps a slot there for exactly this
 * (`projectSwitcher`), and the position is the message: everything below this line is about what
 * this control says. A filter inside one screen can only ever be about that screen.
 *
 * «كذا زيارة خارج هذا العرض» MOVES WITH IT (§10.6.4). A branch's numbers render exactly like the
 * whole shop's — same cards, same words — so the count of what is NOT shown is the only thing
 * stopping an owner from reading one branch's return rate as his business's. It belongs beside the
 * control that caused it, not on the screen that happens to show numbers.
 *
 * AND IT NEVER WIDENS. The options are the branches the SERVER handed this person, already
 * narrowed to what they may read; this component filters nothing and assembles nothing. See
 * `branch-scope.ts` for why that is the one rule this feature cannot bend.
 */
import { Building2 } from 'lucide-react';
import { canSwitch, type ScopeBranch } from './branch-scope';

export function BranchSwitch({
  branches, branch, outside, onChange,
}: {
  /** What the server said this person may read. Never a list built here. */
  branches: ScopeBranch[];
  branch: string;
  /** Visits this view is not showing — 0 on «كل الفروع», where the sentence would be noise. */
  outside?: number;
  onChange: (id: string) => void;
}) {
  // ONE BRANCH IS NO CHOICE, so there is no control. Rendering it would ask a single-branch shop,
  // and every manager scoped to one place, to think about a filter that cannot change anything.
  if (!canSwitch(branches)) return null;

  return (
    <div className="flex flex-col gap-1.5">
      <label className="flex items-center gap-1.5 text-xs text-text-secondary">
        <Building2 size={12} aria-hidden />
        الفرع المعروض
      </label>
      {/* A SELECT RATHER THAN THE PILL ROW «محلّي» USED. The rail is narrow and a chain may have
          a dozen branches: pills wrapped to four lines would push the nav itself off the screen,
          which is a worse cost than one extra tap. */}
      <select
        value={branch}
        onChange={(e) => onChange(e.target.value)}
        aria-label="الفرع المعروض"
        className="w-full rounded-card border border-border-subtle bg-surface-1 px-2 py-1.5 text-sm"
      >
        {/* EMPTY IS EVERYTHING, the same convention the server uses — so «كل الفروع» is not a
            special case anywhere between this control and the query. */}
        <option value="">كل الفروع</option>
        {branches.map((b) => (
          <option key={b.id} value={b.id}>{b.name || 'فرع بلا اسم'}</option>
        ))}
      </select>
      {branch && outside ? (
        <p className="text-xs text-text-secondary">
          {outside} زيارة خارج هذا العرض — في فروعٍ أخرى أو بلا فرع محدَّد.
        </p>
      ) : null}
    </div>
  );
}
