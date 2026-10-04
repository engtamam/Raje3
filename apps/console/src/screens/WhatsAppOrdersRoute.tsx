import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { WhatsAppOrdersScreen } from './WhatsAppOrders';
import { AppGate } from './Locked';

/** «طلبات التوصيل عبر الواتساب» — feature.whatsapp_delivery_orders, same locked-card shape as
 *  every other app row: a shop that has not bought it sees only its own upgrade card. */
export function WhatsAppOrders() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return (
    <AppGate appId="whatsapp-orders" owned={owned} session={session} catalog={catalog}>
      <WhatsAppOrdersScreen session={session} catalog={catalog} />
    </AppGate>
  );
}
