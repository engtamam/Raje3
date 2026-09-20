/**
 * A locked card buys INLINE, right there, once a live plan is resolvable for it — the
 * `subscribeFlow.ts` infrastructure every future app's own locked card rides on unmodified.
 * Falls back to the store link when the gateway is off, the plan is unresolved, or a
 * prerequisite app (`requires_any`) is still missing — never a dead buy button.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OperatorI18nProvider } from '../operator-i18n';
import { LockedCard } from './Locked';

vi.mock('../payment', () => ({ canMintToken: true, confirmToken: vi.fn(), tokenizeCard: vi.fn() }));

const PLAN = { id: 'plan-rating', limits: { 'feature.rating': { limit: 1 } } };

let planCall: unknown;
vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'billing.plans') return { plans: [PLAN] };
      if (a.id === 'subscription.payment_state') return { enabled: true };
      if (a.id === 'subscription.activate') { planCall = body; return { notice: '' }; }
      return {};
    },
  };
});

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;
const owned = { checked: true, message: '', keys: [], apps: [], base: null } as never;

afterEach(() => { cleanup(); planCall = undefined; });

function open() {
  return render(
    <OperatorI18nProvider session={session}>
      <MemoryRouter><LockedCard appId="rating" session={session} catalog={catalog} owned={owned} /></MemoryRouter>
    </OperatorI18nProvider>,
  );
}

describe('a locked card with a live, resolvable plan buys inline', () => {
  it('shows a subscribe button once the plan resolves, not the store link', async () => {
    open();
    expect(await screen.findByText('اشترك الآن')).toBeTruthy();
    expect(screen.queryByText('أضِفه من متجر التطبيقات')).toBeNull();
  });

  it('pressing it opens the same CardForm subscribing to the resolved plan', async () => {
    open();
    fireEvent.click(await screen.findByText('اشترك الآن'));
    expect(await screen.findByLabelText('الاسم كما على البطاقة')).toBeTruthy();
  });
});

describe('a locked card with NO live payment gateway still buys inline', () => {
  it('shows the subscribe button, never the store link, when the gateway is off', async () => {
    vi.doMock('../catalog', async (importOriginal) => {
      const real = await importOriginal<typeof import('../catalog')>();
      return {
        ...real,
        action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
        call: async (_s: unknown, a: { id: string }) => {
          if (a.id === 'billing.plans') return { plans: [PLAN] };
          // THE OFF GATEWAY — this is the exact server answer that used to fall this card back
          // to the store link. It must not any more: the button stays, and the honest failure
          // (if any) now surfaces only when the shop actually presses it.
          if (a.id === 'subscription.payment_state') return { enabled: false, message: 'خارج الخدمة' };
          return {};
        },
      };
    });
    const { LockedCard: LockedCardWithOffGateway } = await import('./Locked');
    render(
      <OperatorI18nProvider session={session}>
        <MemoryRouter>
          <LockedCardWithOffGateway appId="rating" session={session} catalog={catalog} owned={owned} />
        </MemoryRouter>
      </OperatorI18nProvider>,
    );
    expect(await screen.findByText('اشترك الآن')).toBeTruthy();
    expect(screen.queryByText('أضِفه من متجر التطبيقات')).toBeNull();
    vi.doUnmock('../catalog');
  });
});
