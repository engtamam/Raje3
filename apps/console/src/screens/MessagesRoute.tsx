import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { MessagesScreen } from './Messages';
import { type Loading } from '../loading';
import type { Owned } from '../apps';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

export function Messages() {
  // `owned` ALONGSIDE THE CATALOGUE, never instead of it: the catalogue says what this PERSON may
  // do and `owned` says what the SHOP bought. «رسائلي» needs both — the reasons table is the base
  // and belongs to every subscriber, and only the campaigns tab is an app he buys.
  //
  // `branch` (the rail's own «الفرع المعروض»), NEWLY THREADED THROUGH — this screen used to read
  // its own branch list and default its delivery-log filter to «كل الفروع» regardless of what the
  // rest of the console was already narrowed to, the exact «comparing two different shops»
  // BranchSwitch's own module docstring warns about. See MessagesScreen's own note on where this
  // is actually used (the log tab's filter only — the campaigns tab has no branch field at all;
  // a campaign's audience is a choice made per-launch, never the viewing scope — see
  // campaigns-are-company-wide memory).
  const { session, catalog, owned, branch } =
    useOutletContext<ShellContext>();
  return <MessagesScreen session={session} catalog={catalog} owned={owned} branch={branch} />;
}
