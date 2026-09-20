/**
 * Phase أ of «شاشة العملاء والدعم» — wires five already-existing admin action groups (DSAR,
 * consent, legal holds, loyalty reconcile, evidence file) into `CustomerDetail.tsx`'s new
 * "الخصوصية والدعم" tab. Zero new backend work; this only proves the wiring itself: each group
 * calls the right path/method/body, hides politely when its action is absent from the catalog,
 * and every destructive action is gated behind ConfirmDialog before it fires.
 *
 * `findAllByText`/`getAllByText`, NOT the singular form, for anything read off a Table row — the
 * shared `Table` component (rj-ui/Table.tsx) renders BOTH a desktop `<table>` and a stacked
 * mobile "card" view of the same rows at once (CSS picks one), so every cell's text genuinely
 * exists twice in the DOM. This bit every test in this file on the first pass.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import type { AdminAction, AdminCatalog } from './catalog';
import type { Tenant } from './CustomerList';

const calls: { path: string; method: string; body?: unknown }[] = [];
let responder: (path: string, method: string, body?: unknown) => unknown = () => ({});

vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return {
    ...real,
    req: vi.fn(async (path: string, method: string, body?: unknown) => {
      calls.push({ path, method, body });
      const out = responder(path, method, body);
      if (out instanceof Error) throw out;
      return out;
    }),
  };
});

const { CustomerDetail } = await import('./CustomerDetail');
const { AdminRefused } = await import('./api');

const session = { access_token: 'tok' } as never;
const tenant: Tenant = {
  id: 't1', name: 'محل تجريبي', slug: 't1-slug', status: 'active',
  created_at: '2026-01-01T00:00:00Z', updated_at: '2026-01-01T00:00:00Z',
} as never;

function action(id: string, method: AdminAction['method'], path: string): AdminAction {
  return { id, label: id, method, path, capability: 'platform.compliance' };
}

const ALL_ACTIONS = [
  action('compliance.list_dsar', 'GET', '/api/v1/compliance/dsar'),
  action('compliance.open_dsar', 'POST', '/api/v1/compliance/dsar'),
  action('compliance.verify_dsar', 'POST', '/api/v1/compliance/dsar/{dsar_id}/verify'),
  action('compliance.process_dsar', 'POST', '/api/v1/compliance/dsar/{dsar_id}/process'),
  action('compliance.consent_history', 'GET', '/api/v1/compliance/consent/history'),
  action('compliance.grant_consent', 'POST', '/api/v1/compliance/consent/grant'),
  action('compliance.withdraw_consent', 'POST', '/api/v1/compliance/consent/withdraw'),
  action('compliance.list_legal_holds', 'GET', '/api/v1/compliance/legal-holds'),
  action('compliance.place_legal_hold', 'POST', '/api/v1/compliance/legal-holds'),
  action('compliance.release_legal_hold', 'POST', '/api/v1/compliance/legal-holds/{id}/release'),
  action('loyalty.platform_reconcile', 'POST', '/api/v1/loyalty/platform/reconcile'),
  action('loyalty.platform_balance', 'GET', '/api/v1/loyalty/platform/balance'),
  action('loyalty.platform_history', 'GET', '/api/v1/loyalty/platform/history'),
  action('operations.evidence_file', 'POST', '/api/v1/platform/evidence'),
];

function catalogWith(ids: string[]): AdminCatalog {
  return { services: [{ service: 'x', actions: ALL_ACTIONS.filter((a) => ids.includes(a.id)) }],
          unreachable: [] };
}

const FULL_CATALOG = catalogWith(ALL_ACTIONS.map((a) => a.id));

function openPrivacyTab(catalog: AdminCatalog) {
  render(<CustomerDetail session={session} tenant={tenant} subscription={null}
                        planNames={new Map()} catalog={catalog} onClose={() => {}} />);
  fireEvent.click(screen.getByText('الخصوصية والدعم'));
}

/** The FIRST of the two dual-rendered matches (desktop table vs. mobile card) — either works for
 *  a click/assert, since only one is visible at a time and jsdom does not evaluate CSS media
 *  queries, but the first is always the real `<table>` cell in this component's DOM order. */
async function firstMatch(text: string) {
  return (await screen.findAllByText(text))[0];
}

afterEach(() => { cleanup(); calls.length = 0; responder = () => ({}); });

describe('DSAR', () => {
  it('lists existing requests for this tenant', async () => {
    responder = (path) => (path.includes('/dsar') ? { requests: [
      { id: 'd1', tenant: 't1', subject: '966500000000', type: 'export', status: 'pending',
        verified: false, targets: {}, refusal_reason: '', created_at: 0, deadline_at: 0, completed_at: 0 },
    ] } : {});
    openPrivacyTab(FULL_CATALOG);
    expect(await firstMatch('966500000000')).toBeTruthy();
    const listCall = calls.find((c) => c.method === 'GET' && c.path.includes('/dsar'));
    expect(listCall?.path).toContain('tenant=t1');
  });

  it('opens a new DSAR with the typed subject and selected type', async () => {
    responder = () => ({ requests: [] });
    openPrivacyTab(FULL_CATALOG);
    await screen.findByText('لا طلبات خصوصية لهذا المحل');
    fireEvent.change(screen.getByPlaceholderText('رقم جوال صاحب الطلب'), { target: { value: '966511111111' } });
    fireEvent.click(screen.getByText('فتح طلب جديد'));
    await waitFor(() => {
      const openCall = calls.find((c) => c.method === 'POST' && c.path === '/api/v1/compliance/dsar');
      expect(openCall?.body).toEqual({ tenant: 't1', subject: '966511111111', type: 'export' });
    });
  });

  it('shows the server refusal sentence when opening fails', async () => {
    responder = (path, method) => {
      if (method === 'POST' && path === '/api/v1/compliance/dsar') {
        return new AdminRefused('طلب مكرّر لنفس صاحب العلاقة.');
      }
      return { requests: [] };
    };
    openPrivacyTab(FULL_CATALOG);
    await screen.findByText('لا طلبات خصوصية لهذا المحل');
    fireEvent.change(screen.getByPlaceholderText('رقم جوال صاحب الطلب'), { target: { value: '966511111111' } });
    fireEvent.click(screen.getByText('فتح طلب جديد'));
    expect(await screen.findByText('طلب مكرّر لنفس صاحب العلاقة.')).toBeTruthy();
  });

  it('the open button stays disabled with no subject typed', () => {
    responder = () => ({ requests: [] });
    openPrivacyTab(FULL_CATALOG);
    expect((screen.getByText('فتح طلب جديد') as HTMLButtonElement).disabled).toBe(true);
  });

  it('verifying an unverified request sends its typed token and tenant', async () => {
    responder = (path) => {
      if (path.includes('/verify')) return { ok: true };
      return { requests: [
        { id: 'd1', tenant: 't1', subject: '966500000000', type: 'export', status: 'pending',
          verified: false, targets: {}, refusal_reason: '', created_at: 0, deadline_at: 0, completed_at: 0 },
      ] };
    };
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('966500000000');
    fireEvent.change(screen.getAllByPlaceholderText('رمز التحقّق')[0], { target: { value: 'ABC123' } });
    fireEvent.click(screen.getAllByText('تحقّق')[0]);
    await waitFor(() => {
      const verifyCall = calls.find((c) => c.path.includes('/verify'));
      expect(verifyCall?.path).toContain('/api/v1/compliance/dsar/d1/verify');
      expect(verifyCall?.path).toContain('token=ABC123');
      expect(verifyCall?.path).toContain('tenant=t1');
    });
  });

  it('the verify button stays disabled with an empty token', async () => {
    responder = () => ({ requests: [
      { id: 'd1', tenant: 't1', subject: '966500000000', type: 'export', status: 'pending',
        verified: false, targets: {}, refusal_reason: '', created_at: 0, deadline_at: 0, completed_at: 0 },
    ] });
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('966500000000');
    expect((screen.getAllByText('تحقّق')[0] as HTMLButtonElement).disabled).toBe(true);
  });

  it('processing a verified request requires confirmation first', async () => {
    responder = (path) => {
      if (path.includes('/process')) return { ok: true };
      return { requests: [
        { id: 'd1', tenant: 't1', subject: '966500000000', type: 'erase', status: 'pending',
          verified: true, targets: {}, refusal_reason: '', created_at: 0, deadline_at: 0, completed_at: 0 },
      ] };
    };
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('966500000000');
    fireEvent.click(screen.getAllByText('نفّذ')[0]);
    // The confirm dialog is open — the process call has NOT fired yet.
    expect(calls.find((c) => c.path.includes('/process'))).toBeUndefined();
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => {
      const c = calls.find((c) => c.path.includes('/process'));
      expect(c?.path).toContain('/api/v1/compliance/dsar/d1/process');
      expect(c?.path).toContain('tenant=t1');
    });
  });

  it('a completed request offers neither a verify nor a process control', async () => {
    responder = () => ({ requests: [
      { id: 'd1', tenant: 't1', subject: '966500000000', type: 'export', status: 'completed',
        verified: true, targets: { operations: true }, refusal_reason: '',
        created_at: 0, deadline_at: 0, completed_at: 100 },
    ] });
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('966500000000');
    expect(screen.queryByText('تحقّق')).toBeNull();
    expect(screen.queryByText('نفّذ')).toBeNull();
  });

  it('hides the whole section politely when list_dsar is not in the catalog', () => {
    openPrivacyTab(catalogWith([]));
    const section = screen.getByText('طلبات الخصوصية (DSAR)').closest('div');
    expect(section && within(section).getByText('لا صلاحية.')).toBeTruthy();
  });

  it('a failed list read reports the failure, not an empty table', async () => {
    responder = (path) => (path.includes('/dsar') ? new Error('boom') : {});
    openPrivacyTab(FULL_CATALOG);
    expect(await firstMatch('تعذّرت قراءة الطلبات')).toBeTruthy();
  });

  it('selecting "حذف" sends type=erase, not the export default', async () => {
    responder = () => ({ requests: [] });
    openPrivacyTab(FULL_CATALOG);
    await screen.findByText('لا طلبات خصوصية لهذا المحل');
    fireEvent.change(screen.getByPlaceholderText('رقم جوال صاحب الطلب'), { target: { value: '966511111111' } });
    fireEvent.change(screen.getByLabelText('نوع الطلب'), { target: { value: 'erase' } });
    fireEvent.click(screen.getByText('فتح طلب جديد'));
    await waitFor(() => {
      const openCall = calls.find((c) => c.method === 'POST' && c.path === '/api/v1/compliance/dsar');
      expect(openCall?.body).toEqual({ tenant: 't1', subject: '966511111111', type: 'erase' });
    });
  });

  it('a successful open clears a previous failure message', async () => {
    let fail = true;
    responder = (path, method) => {
      if (method === 'POST' && path === '/api/v1/compliance/dsar') {
        if (fail) { fail = false; return new AdminRefused('حدث خطأ ما.'); }
        return {};
      }
      return { requests: [] };
    };
    openPrivacyTab(FULL_CATALOG);
    await screen.findByText('لا طلبات خصوصية لهذا المحل');
    fireEvent.change(screen.getByPlaceholderText('رقم جوال صاحب الطلب'), { target: { value: '966511111111' } });
    fireEvent.click(screen.getByText('فتح طلب جديد'));
    await screen.findByText('حدث خطأ ما.');
    fireEvent.click(screen.getByText('فتح طلب جديد'));
    await waitFor(() => expect(screen.queryByText('حدث خطأ ما.')).toBeNull());
  });

  it('the confirm button is disabled while the process call is in flight', async () => {
    let resolveProcess: (() => void) | undefined;
    responder = (path) => {
      if (path.includes('/process')) {
        return new Promise<{ ok: boolean }>((resolve) => {
          resolveProcess = () => resolve({ ok: true });
        });
      }
      return { requests: [
        { id: 'd1', tenant: 't1', subject: '966500000000', type: 'erase', status: 'pending',
          verified: true, targets: {}, refusal_reason: '', created_at: 0, deadline_at: 0, completed_at: 0 },
      ] };
    };
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('966500000000');
    fireEvent.click(screen.getAllByText('نفّذ')[0]);
    const confirmBtn = screen.getByText('تأكيد') as HTMLButtonElement;
    fireEvent.click(confirmBtn);
    await waitFor(() => expect(confirmBtn.disabled).toBe(true));
    resolveProcess?.();
    await waitFor(() => expect(screen.queryByText('تأكيد')).toBeNull());
  });
});

describe('Consent history', () => {
  it('searches by subject and shows the returned consents', async () => {
    responder = (path) => (path.includes('/consent/history') ? {
      consents: [{ tenant: 't1', subject: '966500000000', purpose: 'تسويق', granted: true,
                  notice_version: '', method: '', expires_at: 0, updated_at: 0,
                  basis: 'self', consented_by: '', relation: '' }],
      proofs: [{ id: 'p1', subject: '966500000000', purpose: 'تسويق', action: 'granted',
                at: 0, actor: 'admin@raje3', basis: 'self' }],
    } : {});
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[0], { target: { value: '966500000000' } });
    fireEvent.click(screen.getAllByText('ابحث')[0]);
    expect((await screen.findAllByText('تسويق')).length).toBeGreaterThan(0);
    expect(await firstMatch('ممنوحة')).toBeTruthy();
    const searchCall = calls.find((c) => c.path.includes('/consent/history'));
    expect(searchCall?.path).toContain('subject=966500000000');
    expect(searchCall?.path).toContain('tenant=t1');
  });

  it('the search button stays disabled with no subject typed', () => {
    openPrivacyTab(FULL_CATALOG);
    expect((screen.getAllByText('ابحث')[0] as HTMLButtonElement).disabled).toBe(true);
  });

  it('shows an empty-history message rather than nothing when the subject has none', async () => {
    responder = () => ({ consents: [], proofs: [] });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[0], { target: { value: '966599999999' } });
    fireEvent.click(screen.getAllByText('ابحث')[0]);
    expect(await firstMatch('لا موافقات مسجَّلة لهذا الرقم')).toBeTruthy();
  });

  it('the grant form only appears after a search has actually run', () => {
    openPrivacyTab(FULL_CATALOG);
    expect(screen.queryByPlaceholderText('الغرض (مثال: تسويق)')).toBeNull();
  });

  it('granting a new purpose sends tenant/subject/purpose and refreshes the history', async () => {
    let granted = false;
    responder = (path) => {
      if (path === '/api/v1/compliance/consent/grant') { granted = true; return {}; }
      return { consents: granted
        ? [{ tenant: 't1', subject: '966500000000', purpose: 'دعم فني', granted: true,
             notice_version: '', method: '', expires_at: 0, updated_at: 0,
             basis: 'self', consented_by: '', relation: '' }]
        : [], proofs: [] };
    };
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[0], { target: { value: '966500000000' } });
    fireEvent.click(screen.getAllByText('ابحث')[0]);
    await screen.findByText('لا موافقات مسجَّلة لهذا الرقم');
    fireEvent.change(screen.getByPlaceholderText('الغرض (مثال: تسويق)'), { target: { value: 'دعم فني' } });
    fireEvent.click(screen.getByText('منح موافقة'));
    await waitFor(() => {
      const c = calls.find((c) => c.path === '/api/v1/compliance/consent/grant');
      expect(c?.body).toEqual({ tenant: 't1', subject: '966500000000', purpose: 'دعم فني' });
    });
    expect(await firstMatch('دعم فني')).toBeTruthy();
  });

  it('the grant button stays disabled with an empty purpose', async () => {
    responder = () => ({ consents: [], proofs: [] });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[0], { target: { value: '966500000000' } });
    fireEvent.click(screen.getAllByText('ابحث')[0]);
    await screen.findByText('لا موافقات مسجَّلة لهذا الرقم');
    expect((screen.getByText('منح موافقة') as HTMLButtonElement).disabled).toBe(true);
  });

  it('withdrawing a granted purpose requires confirmation and sends tenant/subject/purpose', async () => {
    responder = (path) => {
      if (path === '/api/v1/compliance/consent/withdraw') return {};
      return { consents: [{ tenant: 't1', subject: '966500000000', purpose: 'تسويق', granted: true,
                           notice_version: '', method: '', expires_at: 0, updated_at: 0,
                           basis: 'self', consented_by: '', relation: '' }], proofs: [] };
    };
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[0], { target: { value: '966500000000' } });
    fireEvent.click(screen.getAllByText('ابحث')[0]);
    await firstMatch('تسويق');
    fireEvent.click(screen.getAllByText('سحب')[0]);
    // Withdraw is a destructive action too — must not fire before confirmation.
    expect(calls.find((c) => c.path === '/api/v1/compliance/consent/withdraw')).toBeUndefined();
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => {
      const c = calls.find((c) => c.path === '/api/v1/compliance/consent/withdraw');
      expect(c?.body).toEqual({ tenant: 't1', subject: '966500000000', purpose: 'تسويق' });
    });
  });

  it('an already-withdrawn purpose offers no withdraw control', async () => {
    responder = () => ({ consents: [{ tenant: 't1', subject: '966500000000', purpose: 'تسويق',
                                     granted: false, notice_version: '', method: '', expires_at: 0,
                                     updated_at: 0, basis: 'self', consented_by: '', relation: '' }],
                        proofs: [] });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[0], { target: { value: '966500000000' } });
    fireEvent.click(screen.getAllByText('ابحث')[0]);
    await firstMatch('مسحوبة');
    expect(screen.queryByText('سحب')).toBeNull();
  });
});

describe('Legal holds', () => {
  it('lists holds for this tenant on open', async () => {
    responder = (path) => (path.includes('/legal-holds') ? { holds: [
      { id: 'h1', tenant: 't1', subject: '966500000000', reason: 'قضية مفتوحة',
        active: true, placed_at: 0, released_at: 0 },
    ] } : {});
    openPrivacyTab(FULL_CATALOG);
    expect(await firstMatch('قضية مفتوحة')).toBeTruthy();
    const listCall = calls.find((c) => c.method === 'GET' && c.path.includes('/legal-holds'));
    expect(listCall?.path).toContain('tenant=t1');
  });

  it('places a new hold with the typed subject and reason', async () => {
    responder = (path) => (path === '/api/v1/compliance/legal-holds' ? {} : { holds: [] });
    openPrivacyTab(FULL_CATALOG);
    await screen.findByText('لا حجوزات قانونية لهذا المحل');
    fireEvent.change(screen.getAllByPlaceholderText('رقم جوال صاحب العلاقة')[1], { target: { value: '966500000000' } });
    fireEvent.change(screen.getByPlaceholderText('سبب الحجز'), { target: { value: 'قضية مفتوحة' } });
    fireEvent.click(screen.getByText('ضع حجزاً'));
    await waitFor(() => {
      const c = calls.find((c) => c.method === 'POST' && c.path === '/api/v1/compliance/legal-holds');
      expect(c?.body).toEqual({ tenant: 't1', subject: '966500000000', reason: 'قضية مفتوحة' });
    });
  });

  it('the place button stays disabled until both subject and reason are typed', () => {
    responder = () => ({ holds: [] });
    openPrivacyTab(FULL_CATALOG);
    expect((screen.getByText('ضع حجزاً') as HTMLButtonElement).disabled).toBe(true);
  });

  it('releasing an active hold requires confirmation, then calls the hold-specific path', async () => {
    responder = (path) => {
      if (path.includes('/release')) return {};
      return { holds: [{ id: 'h1', tenant: 't1', subject: '966500000000', reason: 'قضية',
                        active: true, placed_at: 0, released_at: 0 }] };
    };
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('قضية');
    fireEvent.click(screen.getAllByText('ارفع الحجز')[0]);
    expect(calls.find((c) => c.path.includes('/release'))).toBeUndefined();
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => {
      const c = calls.find((c) => c.path.includes('/release'));
      expect(c?.path).toBe('/api/v1/compliance/legal-holds/h1/release');
    });
  });

  it('an already-released hold offers no release control', async () => {
    responder = () => ({ holds: [{ id: 'h1', tenant: 't1', subject: '966500000000', reason: 'قضية',
                                  active: false, placed_at: 0, released_at: 1 }] });
    openPrivacyTab(FULL_CATALOG);
    await firstMatch('قضية');
    expect(screen.queryByText('ارفع الحجز')).toBeNull();
  });

  it('hides politely when the catalog carries only the list action', async () => {
    responder = () => ({ holds: [] });
    openPrivacyTab(catalogWith(['compliance.list_legal_holds']));
    await screen.findByText('لا حجوزات قانونية لهذا المحل');
    expect(screen.queryByPlaceholderText('سبب الحجز')).toBeNull();
  });
});

describe('Loyalty (balance/history lookup + reconcile)', () => {
  it('is disabled until both subject_ref and reason are long enough', () => {
    openPrivacyTab(FULL_CATALOG);
    const btn = screen.getByText('أصلح الرصيد') as HTMLButtonElement;
    expect(btn.disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'short' } });
    fireEvent.change(screen.getByPlaceholderText('سبب الإصلاح'), { target: { value: 'ok' } });
    expect(btn.disabled).toBe(true); // subject_ref < 8 chars, reason < 3 chars
  });

  it('reconciles and shows the real was/ledger/drift fields, not a guessed before/after shape', async () => {
    // The REAL response shape (app/core/ledger.py::reconcile) — was/ledger/drift/repaired.
    // An earlier pass here mocked {before, after}, a shape this route has never returned, and
    // the assertions passed anyway because they only checked the mock, never the component's
    // actual field access. Fixed to read the real fields end to end.
    responder = () => ({ subject_ref: 'cust_00012345', was: 120, ledger: 95, drift: 25, repaired: true });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_00012345' } });
    fireEvent.change(screen.getByPlaceholderText('سبب الإصلاح'), { target: { value: 'شكوى عميل' } });
    fireEvent.click(screen.getByText('أصلح الرصيد'));
    // Gated behind confirmation — no call yet.
    expect(calls.find((c) => c.path === '/api/v1/loyalty/platform/reconcile')).toBeUndefined();
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => {
      const c = calls.find((c) => c.path === '/api/v1/loyalty/platform/reconcile');
      expect(c?.body).toEqual({ tenant: 't1', subject_ref: 'cust_00012345', reason: 'شكوى عميل' });
    });
    expect(await screen.findByText('120')).toBeTruthy();
    expect(await screen.findByText('95')).toBeTruthy();
    expect(await screen.findByText('25')).toBeTruthy();
  });

  it('reports "no drift" distinctly when the balance was already correct', async () => {
    responder = () => ({ subject_ref: 'cust_00012345', was: 50, ledger: 50, drift: 0, repaired: false });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_00012345' } });
    fireEvent.change(screen.getByPlaceholderText('سبب الإصلاح'), { target: { value: 'تحقق روتيني' } });
    fireEvent.click(screen.getByText('أصلح الرصيد'));
    fireEvent.click(screen.getByText('تأكيد'));
    expect(await screen.findByText(/لا فرق يُصلَح/)).toBeTruthy();
  });

  it('shows the server refusal sentence rather than a silent no-op', async () => {
    responder = () => new AdminRefused('لا يوجد رصيد لهذا العميل.');
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_00012345' } });
    fireEvent.change(screen.getByPlaceholderText('سبب الإصلاح'), { target: { value: 'شكوى عميل' } });
    fireEvent.click(screen.getByText('أصلح الرصيد'));
    fireEvent.click(screen.getByText('تأكيد'));
    expect(await screen.findByText('لا يوجد رصيد لهذا العميل.')).toBeTruthy();
  });

  it('searching shows the real balance and history before any reconcile happens', async () => {
    responder = (path) => {
      if (path.includes('/platform/balance')) return { points: 340 };
      if (path.includes('/platform/history')) return { entries: [
        { id: 'e1', tenant: 't1', subject_ref: 'cust_00012345', delta: 50, reason: 'earn',
          source: 'v1', actor: '', branch_id: '', balance_after: 340, note: '', created_at: 0 },
        { id: 'e2', tenant: 't1', subject_ref: 'cust_00012345', delta: -10, reason: 'redeem',
          source: 'r1', actor: 'op-1', branch_id: '', balance_after: 290, note: '', created_at: 0 },
      ] };
      return {};
    };
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_00012345' } });
    fireEvent.click(screen.getAllByText('ابحث')[1]);
    // "340" appears both in the KPI card AND in the history table's balance_after column for the
    // first entry — findAllByText, not the singular form, same reason every Table assertion in
    // this file already needs it.
    expect((await screen.findAllByText('340')).length).toBeGreaterThan(0);
    expect(await firstMatch('كسب')).toBeTruthy();
    expect(await firstMatch('استبدال')).toBeTruthy();
    const balCall = calls.find((c) => c.path.includes('/platform/balance'));
    expect(balCall?.path).toContain('tenant=t1');
    expect(balCall?.path).toContain('subject_ref=cust_00012345');
    // No reconcile ever fired just from searching.
    expect(calls.find((c) => c.path === '/api/v1/loyalty/platform/reconcile')).toBeUndefined();
  });

  it('an unknown subject reads as a real, visible zero balance with an empty history', async () => {
    responder = (path) => {
      if (path.includes('/platform/balance')) return { points: 0 };
      if (path.includes('/platform/history')) return { entries: [] };
      return {};
    };
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_neverseen1' } });
    fireEvent.click(screen.getAllByText('ابحث')[1]);
    expect(await screen.findByText('0')).toBeTruthy();
    expect(await screen.findByText('لا حركات نقاط لهذا العميل')).toBeTruthy();
  });

  it('a failed balance read reports the failure, not a stale or blank number', async () => {
    responder = (path) => (path.includes('/platform/balance') ? new Error('boom') : { entries: [] });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_00012345' } });
    fireEvent.click(screen.getAllByText('ابحث')[1]);
    expect(await screen.findByText('تعذّرت قراءة الرصيد.')).toBeTruthy();
  });

  it('a reconcile after a search refreshes the balance shown', async () => {
    let points = 100;
    responder = (path) => {
      if (path === '/api/v1/loyalty/platform/reconcile') { points = 130; return {
        subject_ref: 'cust_00012345', was: 100, ledger: 130, drift: 30, repaired: true }; }
      if (path.includes('/platform/balance')) return { points };
      if (path.includes('/platform/history')) return { entries: [] };
      return {};
    };
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByPlaceholderText('مرجع العميل (subject_ref)'), { target: { value: 'cust_00012345' } });
    fireEvent.click(screen.getAllByText('ابحث')[1]);
    expect(await screen.findByText('100')).toBeTruthy();
    fireEvent.change(screen.getByPlaceholderText('سبب الإصلاح'), { target: { value: 'فرق ظاهر' } });
    fireEvent.click(screen.getByText('أصلح الرصيد'));
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(screen.queryAllByText('130').length).toBeGreaterThan(0));
  });

  it('hides the whole section politely when none of the three loyalty actions is in the catalog', () => {
    openPrivacyTab(catalogWith([]));
    expect(screen.queryByPlaceholderText('مرجع العميل (subject_ref)')).toBeNull();
  });
});

describe('Evidence file', () => {
  it('builds the file, sends the tenant and the converted date window, and renders its sections', async () => {
    responder = () => ({
      tenant: 't1', since: 0, until: 0, generated_at: 0, requested_by: 'admin@raje3',
      sections: {
        privacy_requests: { status: 'read', records: [{ type: 'export' }], count: 1 },
        consent: { status: 'unavailable', records: [], count: 0, reason: 'consent reader not wired' },
      },
    });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.click(screen.getByText('أنشئ ملف الأدلة'));
    // Also gated behind confirmation — the disclosure must never fire on a stray click.
    expect(calls.find((c) => c.path === '/api/v1/platform/evidence')).toBeUndefined();
    fireEvent.click(screen.getByText('تأكيد'));
    expect(await screen.findByText('طلبات الخصوصية')).toBeTruthy();
    expect(await screen.findByText('consent reader not wired')).toBeTruthy();
    const c = calls.find((c) => c.path === '/api/v1/platform/evidence');
    expect(c?.body).toEqual({ tenant: 't1', since: 0, until: 0 });
  });

  it('shows the server refusal sentence on failure, not a blank screen', async () => {
    responder = () => new AdminRefused('لا صلاحية لك بهذا المحل.');
    openPrivacyTab(FULL_CATALOG);
    fireEvent.click(screen.getByText('أنشئ ملف الأدلة'));
    fireEvent.click(screen.getByText('تأكيد'));
    expect(await screen.findByText('لا صلاحية لك بهذا المحل.')).toBeTruthy();
  });

  it('converts typed since/until dates to unix seconds', async () => {
    responder = () => ({ tenant: 't1', since: 0, until: 0, generated_at: 0,
                        requested_by: 'admin@raje3', sections: {} });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.change(screen.getByLabelText('من'), { target: { value: '2026-01-01' } });
    fireEvent.change(screen.getByLabelText('إلى'), { target: { value: '2026-02-01' } });
    fireEvent.click(screen.getByText('أنشئ ملف الأدلة'));
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => {
      const c = calls.find((cc) => cc.path === '/api/v1/platform/evidence');
      const body = c?.body as { tenant: string; since: number; until: number };
      expect(body.tenant).toBe('t1');
      expect(body.since).toBe(Math.floor(new Date('2026-01-01').getTime() / 1000));
      expect(body.until).toBe(Math.floor(new Date('2026-02-01').getTime() / 1000));
    });
  });

  it('an empty date window still builds — since/until default to 0', async () => {
    responder = () => ({ tenant: 't1', since: 0, until: 0, generated_at: 0,
                        requested_by: 'admin@raje3', sections: {} });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.click(screen.getByText('أنشئ ملف الأدلة'));
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => {
      const c = calls.find((cc) => cc.path === '/api/v1/platform/evidence');
      expect(c?.body).toEqual({ tenant: 't1', since: 0, until: 0 });
    });
  });

  it('a section with no records renders no <pre> dump, just its badge', async () => {
    responder = () => ({ tenant: 't1', since: 0, until: 0, generated_at: 0,
                        requested_by: 'admin@raje3',
                        sections: { messages: { status: 'read', records: [], count: 0 } } });
    openPrivacyTab(FULL_CATALOG);
    fireEvent.click(screen.getByText('أنشئ ملف الأدلة'));
    fireEvent.click(screen.getByText('تأكيد'));
    expect(await screen.findByText('الرسائل')).toBeTruthy();
    expect(document.querySelector('pre')).toBeNull();
  });
});

describe('missing actions never crash the tab', () => {
  it('every section reports "لا صلاحية" with an empty catalog, none crash the others', () => {
    openPrivacyTab(catalogWith([]));
    expect(screen.getAllByText('لا صلاحية.').length).toBe(5);
  });

  it('a catalog with only ONE of the five actions still renders the other four as "لا صلاحية"', () => {
    openPrivacyTab(catalogWith(['loyalty.platform_reconcile']));
    expect(screen.getAllByText('لا صلاحية.').length).toBe(4);
    expect(screen.getByPlaceholderText('مرجع العميل (subject_ref)')).toBeTruthy();
  });
});
