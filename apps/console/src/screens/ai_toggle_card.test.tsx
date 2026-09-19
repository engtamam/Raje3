/**
 * «المساعد الذكي عبر واتساب» (on/off) — the shop owner's own kill switch, separate from the
 * subscription itself. A confirm step either direction, and the toggle stays at its OLD value on
 * a failed write.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

let callImpl: (session: unknown, a: { id: string }, body?: unknown) => Promise<unknown>;
let actionIds: Set<string>;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) =>
      actionIds.has(id) ? { id, label: id, method: id.startsWith('operations.set_') ? 'PUT' : 'GET', path: `/${id}` } : undefined,
    call: async (session: unknown, a: { id: string }, body?: unknown) => callImpl(session, a, body),
  };
});

const { AiToggleCard } = await import('./AccountPanes');

afterEach(() => { cleanup(); });

const catalog = { services: [], unreachable: [] } as never;
const session = {} as never;

function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={session}>{ui}</OperatorI18nProvider>);
}

function withToggleActions(extra: string[] = []) {
  actionIds = new Set(['operations.ai_toggle', 'operations.set_ai_toggle', ...extra]);
}

describe('AiToggleCard', () => {
  it('is absent entirely when operations.ai_toggle is not in the catalogue', async () => {
    actionIds = new Set([]);
    callImpl = async () => ({});
    const { container } = render(<AiToggleCard session={session} catalog={catalog} />);
    expect(container.firstChild).toBeNull();
  });

  it('reads back on for a shop that never touched it', async () => {
    withToggleActions();
    callImpl = async (_s, a) => {
      if (a.id === 'operations.ai_toggle') return {};
      return {};
    };
    render(<AiToggleCard session={session} catalog={catalog} />);
    const toggle = await screen.findByTestId('ai-toggle');
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));
  });

  it('turning it off asks for confirmation, then posts enabled:false', async () => {
    withToggleActions();
    let posted: unknown;
    callImpl = async (_s, a, body) => {
      if (a.id === 'operations.ai_toggle') return { enabled: true };
      if (a.id === 'operations.set_ai_toggle') { posted = body; return { enabled: false }; }
      return {};
    };
    render(<AiToggleCard session={session} catalog={catalog} />);
    const toggle = await screen.findByTestId('ai-toggle');
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));

    fireEvent.click(toggle);
    // A CONFIRM DIALOG STANDS BETWEEN THE CLICK AND THE WRITE — the toggle has not moved yet.
    expect(toggle.getAttribute('aria-checked')).toBe('true');
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد' }));

    await waitFor(() => expect(posted).toEqual({ enabled: false }));
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('false'));
  });

  it('a failed write leaves the toggle at its old value', async () => {
    withToggleActions();
    callImpl = async (_s, a) => {
      if (a.id === 'operations.ai_toggle') return { enabled: true };
      if (a.id === 'operations.set_ai_toggle') throw new Error('تعذّر الحفظ.');
      return {};
    };
    render(<AiToggleCard session={session} catalog={catalog} />);
    const toggle = await screen.findByTestId('ai-toggle');
    await waitFor(() => expect(toggle.getAttribute('aria-checked')).toBe('true'));

    fireEvent.click(toggle);
    fireEvent.click(screen.getByRole('button', { name: 'تأكيد' }));

    await screen.findByText('تعذّر الحفظ.');
    expect(toggle.getAttribute('aria-checked')).toBe('true');
  });
});
