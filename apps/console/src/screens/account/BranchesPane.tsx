/**
 * «الفروع» — who works where, and how customers reach that branch. One coherent errand, split
 * into three sections rather than three separate top-level tabs: the branch list/detail, the
 * team inside them, and the WhatsApp number connection (itself a per-branch fact).
 *
 * Mirrors apps/mobile/lib/features/account/branches_screen.dart + branch_detail_screen.dart's OWN
 * SCOPE — mobile gives branches their own pushed destination reached from the account hub; this is
 * the console's wide-layout version of the same destination, reached from the «الفروع» tab.
 */
import { useState } from 'react';
import { Segmented } from '../../rj-ui/Segmented';
import { action, type Catalog } from '../../catalog';
import type { Session } from '../../session';
import { ConnectByBranch } from '../Connect';
import { TeamScreen } from '../Team';
import { type BranchGate } from '../../branches';
import { useOperatorI18n } from '../../operator-i18n';
import '../account-i18n';

export function BranchesPane({ session, catalog, openOnWhatsapp, incomingNotice }: {
  session: Session; catalog: Catalog;
  /** Opens straight on the WhatsApp sub-tab — see AccountScreen's own deep-link handling. */
  openOnWhatsapp?: boolean;
  /** The refusal sentence carried from a subscribe attempt that sent him here. */
  incomingNotice?: string;
}) {
  const { t } = useOperatorI18n();
  const [sub, setSub] = useState<'people' | 'branches' | 'whatsapp'>(
    openOnWhatsapp ? 'whatsapp' : 'people');
  // THE BRANCH TAB'S OWN LOCK — reported by `TeamScreen` once the branches read resolves, since
  // this file has no read of its own to compute it from. `'open'` is the exact same "never lock
  // on an unknown" default `branchGate` itself returns before that.
  const [branchGate, setBranchGate] = useState<BranchGate>('open');

  const SUBTABS = [
    { value: 'people' as const, label: t('account.subtab.people') },
    // THE LOCK IS VISIBLE BEFORE HE PRESSES, not after — through Segmented's own
    // `badge`/`badgeTone`.
    { value: 'branches' as const, label: t('account.subtab.branches'),
     ...(branchGate !== 'open' ? { badge: t('account.subtab.branchesLocked'), badgeTone: 'partial' as const } : {}) },
    { value: 'whatsapp' as const, label: t('account.subtab.whatsapp') },
  ];

  return (
    <div className="flex flex-col gap-4">
      {/* Same Segmented-under-TabBar pattern the top-level tabs use, `size="sm"` marking it as
          nested rather than a second copy of the top-level row — the owner ruled out ever
          stacking two tab strips directly on top of each other. */}
      <Segmented
        size="sm"
        className="grid w-full grid-cols-3 gap-1 sm:flex sm:flex-nowrap [&>button]:w-full [&>button]:truncate sm:[&>button]:flex-1"
        ariaLabel={t('account.branchesSubtabsAriaLabel')}
        value={sub}
        onChange={(v) => setSub(v as typeof sub)}
        options={SUBTABS}
      />

      {sub === 'people' || sub === 'branches' ? (
        <div className="flex flex-col gap-6">
          <TeamScreen session={session} catalog={catalog} tab={sub}
                    onChangeTab={setSub} onBranchGateChange={setBranchGate} />
        </div>
      ) : null}

      {sub === 'whatsapp' ? (
        <div className="flex flex-col gap-6">
          {incomingNotice ? (
            <p role="alert" className="text-sm text-warning">{incomingNotice}</p>
          ) : null}
          {/* PER_BRANCH SHOPS GET ONE CARD A BRANCH — `ConnectByBranch` decides between the single
              establishment-wide card and a list, by reading `shop_mode`.
              THIS IS THE ONLY WHATSAPP CARD LEFT HERE, ON PURPOSE — connecting the number itself
              is a GENERAL establishment fact, not something specific to the assistant bot.
              Everything that configures the ASSISTANT's own behaviour lives at
              `whatsapp-assistant-cards.tsx`, rendered from its own dedicated app screen. */}
          <ConnectByBranch session={session} catalog={catalog} />
        </div>
      ) : null}
    </div>
  );
}

/** Whether «الفروع» has anything at all to show any given role — offered if any one of its three
 *  sections is, so a container tab gated on staff-management alone does not hide WhatsApp
 *  connection from a role that manages neither hiring nor branches. */
export function branchesTabVisible(catalog: Catalog): boolean {
  return Boolean(action(catalog, 'whatsapp.connect_status')
    || action(catalog, 'operations.create_operator')
    || action(catalog, 'operations.list_branches'));
}
