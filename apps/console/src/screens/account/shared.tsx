/**
 * The one piece every «حسابي» sub-screen shares — a quiet, low-emphasis notice card for "nothing
 * to show" and "no permission" states. Kept here rather than duplicated in each sub-screen file,
 * since it carries no domain logic of its own (unlike everything else that moved out of the old
 * single AccountPanes.tsx dump into its own focused file below).
 */
export function Quiet({ children }: { children: React.ReactNode }) {
  return (
    <p className="rounded-card bg-surface-2 p-4 text-sm text-text-secondary">{children}</p>
  );
}
