/**
 * `useSubscribeFlow`'s reaction to the one refusal that is not an ordinary error — an app that
 * cannot be delivered at all without a connected WhatsApp number (`WHATSAPP_CONNECTION_REQUIRED`,
 * services/operations/app/api/v1/subscription.py). This is a real screen-jump, not a banner, so it
 * gets its own focused test rather than living inside locked_inline_subscribe.test.tsx.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { OperatorI18nProvider } from './operator-i18n';
import { useSubscribeFlow } from './subscribeFlow';

const navigateSpy = vi.fn();
vi.mock('react-router-dom', () => ({ useNavigate: () => navigateSpy }));
vi.mock('./payment', () => ({ canMintToken: true, confirmToken: vi.fn(), tokenizeCard: vi.fn() }));

class ServerError extends Error {
  status?: number;
  code?: string;
}

let subscribeShouldFailWith: ServerError | null = null;

vi.mock('./catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('./catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }) => {
      if (a.id === 'billing.plans') return { plans: [] };
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'subscription.activate') {
        if (subscribeShouldFailWith) throw subscribeShouldFailWith;
        return { notice: '' };
      }
      return {};
    },
  };
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function wrapper({ children }: { children: React.ReactNode }) {
  return <OperatorI18nProvider session={session}>{children}</OperatorI18nProvider>;
}

afterEach(() => { vi.clearAllMocks(); subscribeShouldFailWith = null; });

describe('finishSubscribe on WHATSAPP_CONNECTION_REQUIRED', () => {
  it('navigates straight to the whatsapp tab, never shows a generic error', async () => {
    const err = new ServerError('هذا التطبيق يعتمد بالكامل على واتساب الأعمال — اربط رقمك أولاً حتى يعمل.');
    err.status = 409;
    err.code = 'WHATSAPP_CONNECTION_REQUIRED';
    subscribeShouldFailWith = err;

    const { result } = renderHook(() => useSubscribeFlow(session, catalog), { wrapper });
    await act(async () => {
      await result.current.finishSubscribe('plan_campaigns', 'tok_1', 1);
    });

    expect(navigateSpy).toHaveBeenCalledWith(
      '/account?tab=whatsapp',
      { state: { notice: err.message } });
    expect(result.current.error).toBe('');
  });

  it('closes any open card form rather than leaving it stuck mid-payment', async () => {
    const err = new ServerError('لازم تربط رقمك أولاً.');
    err.code = 'WHATSAPP_CONNECTION_REQUIRED';
    subscribeShouldFailWith = err;

    const { result } = renderHook(() => useSubscribeFlow(session, catalog), { wrapper });
    act(() => { result.current.setCardFormPending({ kind: 'subscribe', planId: 'plan_x' }); });
    expect(result.current.cardFormPending).not.toBeNull();

    await act(async () => {
      await result.current.finishSubscribe('plan_x', 'tok_1', 1);
    });
    expect(result.current.cardFormPending).toBeNull();
  });

  it('an ordinary refusal (no matching code) still falls back to the plain error banner', async () => {
    const err = new ServerError('تعذّر إتمام العملية.');
    err.code = 'SOME_OTHER_ERROR';
    subscribeShouldFailWith = err;

    const { result } = renderHook(() => useSubscribeFlow(session, catalog), { wrapper });
    await act(async () => {
      await result.current.finishSubscribe('plan_y', 'tok_1', 1);
    });

    expect(navigateSpy).not.toHaveBeenCalled();
    expect(result.current.error).toBe(err.message);
  });

  it('a thrown non-Error value never crashes and never navigates', async () => {
    subscribeShouldFailWith = 'not an Error instance' as unknown as ServerError;

    const { result } = renderHook(() => useSubscribeFlow(session, catalog), { wrapper });
    await act(async () => {
      await result.current.finishSubscribe('plan_z', 'tok_1', 1);
    });

    expect(navigateSpy).not.toHaveBeenCalled();
    expect(result.current.error).not.toBe('');
  });

  it('a successful subscribe never navigates and clears any prior error', async () => {
    subscribeShouldFailWith = null;
    const { result } = renderHook(() => useSubscribeFlow(session, catalog), { wrapper });
    await act(async () => {
      await result.current.finishSubscribe('plan_ok', 'tok_1', 1);
    });

    expect(navigateSpy).not.toHaveBeenCalled();
    expect(result.current.error).toBe('');
  });
});
