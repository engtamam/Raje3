import { afterEach, describe, expect, it } from 'vitest';
import { remember, takePending } from './pendingPayment';

afterEach(() => sessionStorage.clear());

describe('pendingPayment', () => {
  it('round-trips a subscribe intent', () => {
    remember({ kind: 'subscribe', planId: 'plan_1' });
    expect(takePending()).toEqual({ kind: 'subscribe', planId: 'plan_1' });
  });

  it('round-trips an update_payment_method intent', () => {
    remember({ kind: 'update_payment_method', subscriptionId: 'sub_1' });
    expect(takePending()).toEqual({ kind: 'update_payment_method', subscriptionId: 'sub_1' });
  });

  it('clears itself on the first read — a bookmarked or refreshed callback URL replays nothing', () => {
    remember({ kind: 'subscribe', planId: 'plan_1' });
    expect(takePending()).not.toBeNull();
    expect(takePending()).toBeNull();
  });

  it('returns null rather than throwing on corrupt storage', () => {
    sessionStorage.setItem('raje3.pending_payment.v1', 'not json');
    expect(takePending()).toBeNull();
  });

  it('returns null when nothing was ever remembered', () => {
    expect(takePending()).toBeNull();
  });
});
