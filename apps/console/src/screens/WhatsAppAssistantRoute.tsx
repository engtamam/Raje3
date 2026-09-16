import type { ShellContext } from '../shell-context';
import { useOutletContext } from 'react-router-dom';
import { WhatsAppAssistant } from './WhatsAppAssistant';

export function WhatsAppAssistantRoute() {
  const { session, catalog, owned } = useOutletContext<ShellContext>();
  return <WhatsAppAssistant session={session} catalog={catalog} owned={owned} />;
}
