import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { BookingsScreen } from './Bookings';
import { AppGate } from './Locked';

/**
 * الحجوزات — قسمٌ كامل مغلَق بالتطبيق، مثل «نقاطي». محلٌّ لم يشترِ نظام الحجوزات يرى بطاقة
 * الترقية هنا فقط؛ ولا يفقد شيئاً في «تسجيل زيارة» أو «عملائي» — القاعدة نفسها في كل تطبيق.
 */
export function Bookings() {
  const { session, owned, branch, branches, setBranch } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="bookings" owned={owned}>
      <BookingsScreen session={session} branch={branch} branches={branches} onBranch={setBranch} />
    </AppGate>
  );
}
