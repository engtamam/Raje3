import type { ShellContext } from '../shell-context';
import { useLocation, useOutletContext, useSearchParams } from 'react-router-dom';
import { AccountScreen, type PaneLink } from './account/AccountScreen';
import { type Loading } from '../loading';
import type { Owned } from '../apps';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

const PANES = ['billing', 'invoices', 'whatsapp', 'shop', 'team', 'keys', 'login', 'data'] as const;

export function Account() {
  const { session, catalog, owned } =
    useOutletContext<ShellContext>();
  const [params] = useSearchParams();
  // VALIDATED AGAINST THE LIST, never passed through. `?tab=` comes from a URL anybody can type,
  // and an unknown value would leave the screen on a tab that does not exist — a blank page
  // reached from a button that promised a purchase.
  //
  // THE LIST STILL HOLDS FOUR NAMES THAT ARE NO LONGER TABS. They are sections now, inside two of
  // the four that remain, and `resolvePane` sends each to the page that holds it — every link
  // already sent, bookmarked or printed still lands on the right screen.
  const asked = params.get('tab') ?? '';
  const openOn = (PANES as readonly string[]).includes(asked) ? (asked as PaneLink) : undefined;
  // subscribeFlow.ts's own WHATSAPP_CONNECTION_REQUIRED redirect (`navigate(..., {state:
  // {notice}})`) — react-router `state`, never a URL param: free text, gone the moment he leaves
  // this page, exactly like any other one-time toast.
  const notice = (useLocation().state as { notice?: string } | null)?.notice;
  return <AccountScreen session={session} catalog={catalog} openOn={openOn} owned={owned}
                       notice={notice} />;
}
