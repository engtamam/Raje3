/**
 * «تسجيل جهات الاتصال تلقائياً عبر واتساب» — gated ONLY by the outer `<AppGate appId="whatsapp">`
 * (Account.tsx) now, not by a second, redundant `feature.contacts` check inside the card itself
 * (2026-09-12 correction — see the card's own header note: `feature.contacts` is free for every
 * shop, so that inner check never actually excluded anyone with WhatsApp connected).
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import { OperatorI18nProvider } from '../operator-i18n';
import { WhatsAppAutoRegisterCard } from './whatsapp-assistant-cards';

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;

let readEnabled = false;
vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: { enabled?: boolean }) => {
      if (a.id === 'operations.whatsapp_auto_register') return { enabled: readEnabled };
      if (a.id === 'operations.set_whatsapp_auto_register') { readEnabled = Boolean(body?.enabled); return { enabled: readEnabled }; }
      return {};
    },
  };
});

const catalog = { services: [], unreachable: [] } as never;

function render() {
  return rtlRender(
    <OperatorI18nProvider session={SESSION}>
      <WhatsAppAutoRegisterCard session={SESSION} catalog={catalog} />
    </OperatorI18nProvider>,
  );
}

afterEach(() => { cleanup(); readEnabled = false; });

describe('WhatsAppAutoRegisterCard', () => {
  it('renders with no `owned`/ownership prop at all — the outer AppGate is the only gate now', async () => {
    render();
    await waitFor(() => expect(screen.getByTestId('whatsapp-auto-register-toggle')).toBeTruthy());
  });

  it('flipping it on asks for confirmation, then saves', async () => {
    render();
    const toggle = await screen.findByTestId('whatsapp-auto-register-toggle');
    fireEvent.click(toggle);
    const confirmButtons = await screen.findAllByRole('button');
    const confirm = confirmButtons.find((b) => /تفعيل|فعّل|تأكيد/.test(b.textContent ?? ''));
    expect(confirm).toBeTruthy();
    fireEvent.click(confirm!);
    await waitFor(() => expect(readEnabled).toBe(true));
  });
});
