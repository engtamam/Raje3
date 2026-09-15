/**
 * «خدمات متنقلة» — the review queue: status filters, the pending accept/reject pair, the
 * accepted done/no-show pair, the needs-decision check (the request's own REAL appointment
 * moment — `requested_time`, a real validated epoch instant — has passed and it is still open;
 * see MobileRequests.tsx's own module docstring), the risk badge, and the map link. Each backend
 * call faked at the `catalog.call` boundary, same discipline as coupons.test.tsx.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';
import { MobileRequestsScreen } from './MobileRequests';

const SESSION = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
const NOW = Math.floor(Date.now() / 1000);

const PENDING = {
  id: 'mreq_1', tenant: 't1', phone: '+966501112222', customer_name: 'نورة العنزي',
  service_ids: ['svc_wash'], requested_time: NOW + 3600, lat: 24.7, lng: 46.6,
  status: 'pending', created: NOW - 600, decided_at: 0, decided_by: '', reject_reason: '',
  visit_id: '', note: '', maps_url: 'https://www.google.com/maps?q=24.7,46.6',
};
const ACCEPTED_RECENT = {
  ...PENDING, id: 'mreq_2', customer_name: 'خالد المطيري', status: 'accepted',
  requested_time: NOW - 300, decided_at: NOW - 300,
};
const ACCEPTED_OVERDUE = {
  ...PENDING, id: 'mreq_3', customer_name: 'هند العتيبي', status: 'accepted',
  requested_time: NOW - 4 * 3600, decided_at: NOW - 4 * 3600,
};
const COMPLETED = {
  ...PENDING, id: 'mreq_4', customer_name: 'عبدالله الشمري', status: 'completed',
  requested_time: NOW - 86400, decided_at: NOW - 86400, created: NOW - 86400, visit_id: 'v1',
};

let acceptCalls: Record<string, unknown>[] = [];
let rejectCalls: Record<string, unknown>[] = [];
let completeCalls: Record<string, unknown>[] = [];
let noShowCalls: Record<string, unknown>[] = [];
let rows = [PENDING, ACCEPTED_RECENT, ACCEPTED_OVERDUE, COMPLETED];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, params?: Record<string, unknown>) => {
      if (a.id === 'operations.mobile_requests_list') return { requests: rows };
      if (a.id === 'operations.manage_services' || a.id === 'operations.list_services') {
        return { services: [{ id: 'svc_wash', name: 'غسيل خارجي' }] };
      }
      if (a.id === 'operations.mobile_request_risk') {
        const id = String(params?.request_id ?? '');
        return { considered: 5, no_shows: id === 'mreq_1' ? 3 : 0, risky: id === 'mreq_1', threshold_percent: 40 };
      }
      if (a.id === 'operations.mobile_request_accept') { acceptCalls.push(params ?? {}); return { ...PENDING, status: 'accepted' }; }
      if (a.id === 'operations.mobile_request_reject') { rejectCalls.push(params ?? {}); return { ...PENDING, status: 'rejected' }; }
      if (a.id === 'operations.mobile_request_complete') { completeCalls.push(params ?? {}); return { ...ACCEPTED_RECENT, status: 'completed' }; }
      if (a.id === 'operations.mobile_request_no_show') { noShowCalls.push(params ?? {}); return { ...ACCEPTED_RECENT, status: 'no_show' }; }
      return {};
    },
  };
});

const catalog = { services: [], unreachable: [] } as never;

function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION}>{ui}</OperatorI18nProvider>);
}

afterEach(() => {
  cleanup();
  acceptCalls = []; rejectCalls = []; completeCalls = []; noShowCalls = [];
  rows = [PENDING, ACCEPTED_RECENT, ACCEPTED_OVERDUE, COMPLETED];
  vi.restoreAllMocks();
});

describe('«خدمات متنقلة»', () => {
  it('lists every request and resolves service names from the real catalogue', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getAllByText('نورة العنزي').length).toBeGreaterThan(0));
    expect(screen.getAllByText('غسيل خارجي').length).toBeGreaterThan(0);
  });

  it('a pending request offers accept/reject, and accept calls the real action with its id', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const acceptBtn = await screen.findByTestId('mobile-request-accept-mreq_1');
    fireEvent.click(acceptBtn);
    await waitFor(() => expect(acceptCalls).toEqual([{ request_id: 'mreq_1' }]));
  });

  it('reject prompts for a reason and sends it', async () => {
    vi.spyOn(window, 'prompt').mockReturnValue('بعيد عن نطاق الخدمة');
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const rejectBtn = await screen.findByTestId('mobile-request-reject-mreq_1');
    fireEvent.click(rejectBtn);
    await waitFor(() => expect(rejectCalls).toEqual([{ request_id: 'mreq_1', reason: 'بعيد عن نطاق الخدمة' }]));
  });

  it('an accepted request recently decided offers done/no-show, and done calls the real action', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const completeBtn = await screen.findByTestId('mobile-request-complete-mreq_2');
    fireEvent.click(completeBtn);
    await waitFor(() => expect(completeCalls).toEqual([{ request_id: 'mreq_2' }]));
  });

  it('no-show calls the real action', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const noShowBtn = await screen.findByTestId('mobile-request-noshow-mreq_2');
    fireEvent.click(noShowBtn);
    await waitFor(() => expect(noShowCalls).toEqual([{ request_id: 'mreq_2' }]));
  });

  it('an accepted request open for hours surfaces as «تحتاج قرار» with its own KPI and banner', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getByTestId('mobile-requests-kpi-needs-decision').textContent).toContain('1'));
    expect(screen.getByTestId('mobile-requests-banner-go')).toBeTruthy();
    expect(screen.getAllByText('الموعد فات — بانتظار «تم / لم يتم»').length).toBeGreaterThan(0);
  });

  it('the banner filters the list down to only the overdue request', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const goBtn = await screen.findByTestId('mobile-requests-banner-go');
    fireEvent.click(goBtn);
    await waitFor(() => expect(screen.getAllByTestId('mobile-request-card').length).toBe(1));
    expect(screen.getByText('هند العتيبي')).toBeTruthy();
  });

  it('a pending request the risk check flags as risky shows the warning', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getByText('عميل معرّض لعدم الحضور')).toBeTruthy());
  });

  it('a completed request carries no action buttons', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getAllByText('عبدالله الشمري').length).toBeGreaterThan(0));
    expect(screen.queryByTestId('mobile-request-complete-mreq_4')).toBeNull();
    expect(screen.queryByTestId('mobile-request-accept-mreq_4')).toBeNull();
  });

  it('search narrows the list by name', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    await waitFor(() => expect(screen.getAllByTestId('mobile-request-card').length).toBe(4));
    fireEvent.change(screen.getByPlaceholderText('بحث بالاسم أو الجوال'), { target: { value: 'خالد' } });
    await waitFor(() => expect(screen.getAllByTestId('mobile-request-card').length).toBe(1));
  });

  it('every card links out to the real maps url the backend computed', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const links = await screen.findAllByText('فتح الموقع بالخرائط');
    expect((links[0].closest('a') as HTMLAnchorElement).href).toBe('https://www.google.com/maps?q=24.7,46.6');
  });

  it('the phone number opens wa.me with just the digits, no plus sign', async () => {
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const link = (await screen.findAllByText('+966501112222'))[0].closest('a') as HTMLAnchorElement;
    expect(link.href).toBe('https://wa.me/966501112222');
    expect(link.target).toBe('_blank');
  });

  it('copying the phone number writes it to the clipboard', async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<MobileRequestsScreen session={SESSION} catalog={catalog} />);
    const copyBtn = (await screen.findAllByTitle('نسخ رقم الجوال'))[0];
    fireEvent.click(copyBtn);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith('+966501112222'));
  });
});
