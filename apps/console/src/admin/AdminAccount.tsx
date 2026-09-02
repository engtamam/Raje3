/**
 * حسابي — أول شي حقيقي هنا (بدل `ComingSoon`): زر تسجيل الخروج، ولا شي غيره اليوم.
 *
 * FOUND LIVE: `useAdminSession()` already returns a working `signOut` (session.ts) — AdminPortal.tsx
 * simply never destructured it, and the "حسابي" tab rendered `<ComingSoon />`, so THE WHOLE ADMIN
 * PANEL HAD NO SIGN-OUT BUTTON ANYWHERE. Not reachable by any path — an operator who needed a fresh
 * token (a capability just granted to their role, for instance) had no way to get one without
 * clearing storage by hand. Mirrors `../affiliates/AffiliateAccount.tsx`'s own sign-out button
 * exactly — same product, same pattern, that screen just already had it.
 */
import { LogOut } from 'lucide-react';
import { Button } from '../rj-ui/Button';

export function AdminAccount({ onSignOut }: { onSignOut: () => void }) {
  return (
    <div className="flex flex-col gap-4 p-6">
      <h1 className="text-2xl leading-tight tracking-tight">حسابي</h1>
      <Button type="button" variant="outline" onClick={onSignOut}
             className="flex items-center justify-center gap-2 text-danger">
        <LogOut size={16} /> تسجيل الخروج
      </Button>
    </div>
  );
}
