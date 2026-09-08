/**
 * «Connect» — the "اربط واتساب" button's own readiness now depends on a runtime fetch
 * (`GET /whatsapp/config`), not a build-time env var (2026-09-08 change, see meta.ts's own
 * docstring). This covers the three real states: configured, not configured, and the fetch
 * itself failing — the last one must degrade to the exact same sentence as "not configured",
 * never a distinct error or a hung button.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';

const calls: { id: string }[] = [];
let metaConfigResponse: unknown = { configured: false };
let metaConfigShouldThrow = false;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      calls.push({ id: a.id });
      if (a.id === 'whatsapp.meta_config') {
        if (metaConfigShouldThrow) throw new Error('network down');
        return metaConfigResponse;
      }
      if (a.id === 'whatsapp.connect_status') {
        return { state: '', message: 'لم تبدأ الربط بعد.', can_send: false };
      }
      return {};
    },
  };
});

// `loadMetaSdk` itself (the FB script load) is exercised by meta.test — this file is about
// Connect.tsx's own wiring of the fetched config into it, so the SDK step is stubbed to whatever
// `MetaConfig.configured` says, without touching `window.FB` or the network at all.
vi.mock('../meta', async (importOriginal) => {
  const real = await importOriginal<typeof import('../meta')>();
  return {
    ...real,
    loadMetaSdk: async (cfg: { configured?: boolean } | null) =>
      cfg?.configured ? 'ready' : 'unconfigured',
    metaSdk: () => null,
  };
});

const { Connect } = await import('./Connect');

afterEach(() => { cleanup(); calls.length = 0; metaConfigShouldThrow = false; });

const catalog = { services: [], unreachable: [] } as never;
const session = {} as never;

describe('Connect — the popup button reads its readiness from GET /whatsapp/config', () => {
  it('stays disabled with the honest sentence when the backend says not configured', async () => {
    metaConfigResponse = { app_id: '', config_id: '', graph_version: '', configured: false };
    render(<Connect session={session} catalog={catalog} state={undefined} onChange={() => {}} />);
    await waitFor(() => expect(calls.some((c) => c.id === 'whatsapp.meta_config')).toBe(true));
    await waitFor(() => expect(screen.getByRole('button', { name: 'تعذّر فتح الربط الآن' })).toBeTruthy());
    expect((screen.getByRole('button', { name: 'تعذّر فتح الربط الآن' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText('عُطلٌ من عندنا، لا في حسابك — تواصل معنا ونكمل معك الربط.')).toBeTruthy();
  });

  it('enables the button once the backend says configured', async () => {
    metaConfigResponse = { app_id: '123', config_id: '456', graph_version: 'v26.0', configured: true };
    render(<Connect session={session} catalog={catalog} state={undefined} onChange={() => {}} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'اربط واتساب' })).toBeTruthy());
    expect((screen.getByRole('button', { name: 'اربط واتساب' }) as HTMLButtonElement).disabled).toBe(false);
  });

  it('a failed config fetch degrades to the SAME unconfigured state — ours, never a distinct error', async () => {
    metaConfigShouldThrow = true;
    render(<Connect session={session} catalog={catalog} state={undefined} onChange={() => {}} />);
    await waitFor(() => expect(screen.getByRole('button', { name: 'تعذّر فتح الربط الآن' })).toBeTruthy());
    expect(screen.getByText('عُطلٌ من عندنا، لا في حسابك — تواصل معنا ونكمل معك الربط.')).toBeTruthy();
  });
});
