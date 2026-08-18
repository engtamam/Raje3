/**
 * «متجر التطبيقات» — the address behind the name every other screen already printed.
 *
 * WHY IT IS A ROUTE AND NOT A LINK WITH A QUERY. Four screens send an owner here — the locked
 * card of every app he has not bought, and the branch cap in «منشأتي» — and all of them pointed
 * at `/account?tab=billing`: a place with no row in the rail, no name of its own, and a tab
 * labelled something else when he arrived. He read «رقِّ باقتك من «متجر التطبيقات»», went looking
 * for it, and found four tabs none of which carried that name.
 *
 * A row in the rail needs a path the shell can match to highlight it, and a query string is not
 * one. So the store has an address, and it renders the screen that already sells — not a second
 * copy of it. The pane it opens on is the same pane `?tab=billing` opens, because a bookmark, a
 * printed link and this row must all land on one screen rather than on two that drift.
 */
import { useOutletContext } from 'react-router-dom';
import type { ShellContext } from '../shell-context';
import { AccountScreen } from './Account';

export function Store() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return <AccountScreen session={session} catalog={catalog} openOn="billing" owned={owned} />;
}
