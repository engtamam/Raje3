/**
 * What every screen is handed by the shell — written once.
 *
 * IT WAS WRITTEN NINE TIMES. Each `*Route.tsx` declared its own inline shape for
 * `useOutletContext`, so the app had nine independent opinions about what the shell provides. That
 * is survivable while the shape never changes, and it is exactly the arrangement this codebase has
 * already paid for twice: the fills vocabulary lived in four files and one update rejected all 66
 * templates; the branch scope lived in two readers and they disagreed about `marketing`.
 *
 * THE COST IS NOT THE TYPING, IT IS THE SILENCE. A screen whose inline type omits `branch` does not
 * fail to compile — it simply never reads it, and renders the whole chain while the rail says
 * «الرياض». Nothing anywhere reports that; the screen looks healthy and answers a question nobody
 * asked. One exported type makes the omission a compile error instead of a wrong number.
 */
import type { Catalog } from './catalog';
import type { Loading } from './loading';
import type { Owned } from './apps';
import type { ScopeBranch } from './branch-scope';
import type { Session } from './session';

export interface ShellContext {
  session: Session;
  catalog: Catalog;
  /** What the SHOP bought. Read once in `App`, because five screens asking is five round trips. */
  owned: Loading<Owned>;
  /**
   * The branch every screen is currently scoped to — "" for the whole establishment.
   *
   * ALREADY VALIDATED AGAINST WHAT HE MAY READ: `App` passes it through `currentBranch`, so a
   * stored id belonging to a branch he has since lost resolves back to «everything» rather than
   * to a screen that silently returns nothing.
   */
  branch: string;
  /** The branches he may read, as the server narrowed them. The switcher's only source. */
  branches: ScopeBranch[];
  /**
   * Change the scope from inside a screen — «محلّي» offers a supervisor «اختر فرعاً» when his
   * dashboard covers several, and that pick must be the SAME choice the rail holds. A screen with
   * its own copy of the state is the split this whole feature exists to close.
   */
  setBranch: (id: string) => void;
}
