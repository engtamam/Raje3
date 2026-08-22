/**
 * «حسابي» (2026-08-22) — replaces the stub. Sign-out moved HERE from Home's own header (Tamam:
 * "حسابي تكون تحت على الشريط وفيها تسجيل خروج") — Home is only one of five tabs now, so a control
 * that lived in its header was invisible from every other screen. The account tab is the one
 * destination every role always has, so it is the one place a control that must always be
 * reachable can actually live.
 */
import { useEffect, useState } from 'react';
import { CircleUserRound, LogOut } from 'lucide-react';
import { Button } from '@base-ui/design-system/Button';
import { Skeleton } from '@base-ui/design-system/Skeleton';
import { me, type AffiliateSession, type Me } from './api';

const ROLE_LABEL: Record<string, string> = {
  affiliate_manager: 'مدير تسويق', affiliate_promoter: 'مسوّق',
};

export function AffiliateAccount({ session, onSignOut }: {
  session: AffiliateSession; onSignOut: () => void;
}) {
  const [who, setWho] = useState<Me | 'loading' | 'failed'>('loading');

  useEffect(() => {
    let cancelled = false;
    me(session).then((m) => { if (!cancelled) setWho(m); })
      .catch(() => { if (!cancelled) setWho('failed'); });
    return () => { cancelled = true; };
  }, [session]);

  return (
    <div className="flex flex-col gap-6 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">حسابي</h1>

      {who === 'loading' ? (
        <Skeleton height={90} />
      ) : (
        <div className="flex items-center gap-3 rounded-card bg-surface-1 p-4 shadow-sm">
          <div className="grid size-12 shrink-0 place-items-center rounded-full bg-surface-2 text-text-muted">
            <CircleUserRound size={24} />
          </div>
          <div className="flex flex-col">
            <span className="font-medium">
              {who === 'failed' ? 'تعذّرت قراءة بيانات حسابك' : who.name}
            </span>
            {who !== 'failed' ? (
              <span className="text-sm text-text-secondary">{ROLE_LABEL[who.role] ?? who.role}</span>
            ) : null}
          </div>
        </div>
      )}

      <Button type="button" variant="outline" onClick={onSignOut}
             className="flex items-center justify-center gap-2 text-danger">
        <LogOut size={16} /> تسجيل الخروج
      </Button>
    </div>
  );
}
