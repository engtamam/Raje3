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
import { Building2, Plus } from 'lucide-react';
import { canSwitch, type ScopeBranch } from './branch-scope';
import { hasFailed, isDenied, isLoading, isReady, type Loading } from './loading';
import { action, type Catalog } from './catalog';

export function BranchSwitch({
  branches, branch, outside, onChange, catalog, onAdd,
}: {
  /** What the server said this person may read — WITH its not-a-value states intact.
   *
   *  IT USED TO ARRIVE AS A PLAIN ARRAY, and the shell collapsed «could not read» into `[]` one
   *  line before rendering. So a chain of four branches whose scope read failed saw exactly what
   *  a single-branch shop sees: no control, no sentence, nothing. Its screens stayed unnarrowed
   *  and its owner never learned that the choice existed and had not been offered.
   *
   *  The three states are kept apart all the way here, because here is where they mean different
   *  things to a person. */
  branches: Loading<ScopeBranch[]>;
  branch: string;
  /** Visits this view is not showing — 0 on «كل الفروع», where the sentence would be noise. */
  outside?: number;
  onChange: (id: string) => void;
  /** What this person may do — the button below is drawn from the capability, never from a role. */
  catalog: Catalog;
  /** Opens the shop's own «add a branch» flow. Absent where there is nowhere to open it. */
  onAdd?: () => void;
}) {
  // NOTHING WHILE IT IS STILL COMING. A control that flickers into existence a beat after the rail
  // draws is one an eye follows instead of the nav.
  if (isLoading(branches)) return null;

  // OURS, AND SAID SO. He can do nothing about it — but he must know his screens are showing the
  // whole chain because we could not read his scope, not because he has one branch.
  if (hasFailed(branches)) {
    return (
      <p className="flex items-center gap-1.5 text-xs text-text-secondary">
        <Building2 size={12} aria-hidden />
        تعذّرت قراءة فروعك — الأرقام تعرض المحل كاملاً.
      </p>
    );
  }

  // DENIED IS ITS OWN STATE AND ITS OWN SILENCE. A person whose role does not carry the scope read
  // is not being told anything is wrong: nothing about branches concerns him.
  if (isDenied(branches)) return null;

  const list: ScopeBranch[] = isReady(branches) ? branches : [];

  /* ── ADDING ONE FROM HERE, ANSWERING THE QUESTION THIS FEATURE STARTED FROM ─────────────────
     «هل ممكن نخلي انشاء الفروع من المبدل نفسه، يضغط وينشئ فرع لو عنده الصلاحية؟»

     The moment a person wants a second branch is the moment he is looking at this control and
     finding nothing to switch to. Sending him to «حسابي ← منشأتي ← الفروع» and back is three
     screens of travel for one name — and travel is what makes a person put a thing off.

     ON THE CAPABILITY, NOT ON THE ROLE. The button exists only when the catalogue carries
     `operations.create_branch`, which the gateway already filtered by what this person may do. A
     manager sees it; a branch supervisor never learns it was there, which is right: he cannot use
     it and an offer he cannot take is a small lie repeated every day. */
  const canAdd = Boolean(onAdd && action(catalog, 'operations.create_branch'));

  // ONE BRANCH IS NO CHOICE, so there is no control — UNLESS he may add one. A single-branch shop
  // whose owner can open a second still needs the door; what it does not need is a filter.
  if (!canSwitch(list)) {
    return canAdd ? (
      <button
        type="button"
        onClick={onAdd}
        className="group flex items-center gap-2 rounded-lg border border-dashed border-border-subtle
                   px-2.5 py-1.5 text-xs font-medium text-text-secondary transition-all duration-150
                   hover:border-accent/50 hover:bg-surface-2 hover:text-accent-on-soft"
      >
        <span className="grid size-5 shrink-0 place-items-center rounded-md bg-surface-2 text-text-muted
                          ring-1 ring-border-subtle/60 transition-all duration-150
                          group-hover:bg-accent/10 group-hover:text-accent-on-soft group-hover:ring-accent/20
                          group-hover:scale-105">
          <Plus size={12} aria-hidden />
        </span>
        أضف فرعاً
      </button>
    ) : null;
  }

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
        {list.map((b) => (
          <option key={b.id} value={b.id}>{b.name || 'فرع بلا اسم'}</option>
        ))}
      </select>
      {/* NOT AN OPTION INSIDE THE SELECT. «+ فرع جديد» as a row in the list would be an item that
          is not a branch sitting among branches — and one mis-tap would change what every screen
          is showing him on the way to a form he did not want. A separate control cannot be hit by
          accident while choosing. */}
      {canAdd ? (
        <button
          type="button"
          onClick={onAdd}
          className="group flex items-center gap-2 self-start rounded-lg px-2 py-1 text-xs font-medium
                     text-accent-on-soft transition-all duration-150 hover:bg-surface-2"
        >
          <span className="grid size-5 shrink-0 place-items-center rounded-md bg-accent/10 text-accent-on-soft
                            ring-1 ring-accent/20 transition-transform duration-150 group-hover:scale-105">
            <Plus size={12} aria-hidden />
          </span>
          أضف فرعاً
        </button>
      ) : null}
      {branch && outside ? (
        <p className="text-xs text-text-secondary">
          {outside} زيارة خارج هذا العرض — في فروعٍ أخرى أو بلا فرع محدَّد.
        </p>
      ) : null}
    </div>
  );
}
