/**
 * سجل الأخطاء — الاختبارات تثبّت أن الشاشة تعرض المصدرين في قائمة واحدة، وأن الفلاتر تُبنى من
 * البيانات لا من قائمة مكتوبة هنا، وأن «لا نتائج» ليست «كل شيء سليم».
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminSignals, signalToText, type Signal } from './AdminSignals';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'error-collector', actions: [
      { id: 'errors.list', label: 'سجل الأخطاء', method: 'GET' as const,
        path: '/api/v1/signals', capability: 'platform.observability', group: 'المنصة' },
    ] },
  ],
  unreachable: [],
};

const POD: Signal = {
  id: 's1', received_at: 1_760_000_100, occurred_at: 1_760_000_090,
  source: 'server_log', severity: 'error', service: 'loyalty',
  status_code: 500, request_id: 'req-abc',
  message: 'connection refused talking to postgres',
  detail: { exception: 'ConnectionRefusedError' },
  context: { pod: 'loyalty-6d4f', namespace: 'base-services' },
};

const BROWSER: Signal = {
  id: 's2', received_at: 1_760_000_200, occurred_at: 1_760_000_200,
  source: 'browser', severity: 'error', service: 'console',
  status_code: null, request_id: '',
  message: "TypeError: Cannot read properties of undefined (reading 'map')",
  detail: { kind: 'onerror' },
  context: { url: 'https://admin.raje3.sa/bookings' },
};

function page(signals: Signal[]) {
  return {
    signals,
    next_cursor: null,
    sources: Array.from(new Set(signals.map((s) => s.source))),
    severities: Array.from(new Set(signals.map((s) => s.severity))),
    services: Array.from(new Set(signals.map((s) => s.service))),
  };
}

let fetchCatalogMock: ReturnType<typeof vi.fn>;
let reqMock: ReturnType<typeof vi.fn>;

vi.mock('./catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('./catalog')>();
  return { ...real, fetchCatalog: (...args: unknown[]) => fetchCatalogMock(...args) };
});
vi.mock('./api', async (importOriginal) => {
  const real = await importOriginal<typeof import('./api')>();
  return { ...real, req: (...args: unknown[]) => reqMock(...args) };
});

afterEach(() => vi.clearAllMocks());

describe('AdminSignals', () => {
  it('shows a pod error and a browser error in ONE list', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText(POD.message)).toBeTruthy());
    expect(screen.getByText(BROWSER.message)).toBeTruthy();
    // The two sources are badges on rows of one list, never two tabs. `getAllByText` because each
    // value also appears once as its own filter checkbox — which is the point of the filters being
    // built from the data.
    expect(screen.getAllByText('server_log').length).toBeGreaterThan(0);
    expect(screen.getAllByText('browser').length).toBeGreaterThan(0);
    expect(screen.getByText('loyalty')).toBeTruthy();
    expect(screen.getByText('console')).toBeTruthy();
  });

  it('defaults to severity=error and a 24h window, and says so in the request', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalled());
    const url = String((reqMock.mock.calls[0] as unknown[])[0]);
    const params = new URLSearchParams(url.split('?')[1]);
    expect(params.getAll('severity')).toEqual(['error']);
    const since = Number(params.get('since'));
    const expected = Math.floor(Date.now() / 1000) - 24 * 3600;
    expect(Math.abs(since - expected)).toBeLessThan(60);
  });

  it('builds its filter checkboxes from the values the API returned, not from a list in the code',
     async () => {
    // A severity nothing on this platform has ever emitted before. It must become a checkbox with
    // no console release — that is the whole point of the column being a free-form string.
    const surprise: Signal = { ...POD, id: 's3', severity: 'warning', source: 'mobile_app' };
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([surprise, POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('warning')).toBeTruthy());
    expect(screen.getByLabelText('mobile_app')).toBeTruthy();
    expect((screen.getByLabelText('error') as HTMLInputElement).checked).toBe(true);
    expect((screen.getByLabelText('warning') as HTMLInputElement).checked).toBe(false);
  });

  it('ticking a source sends it as a repeated query param', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('browser')).toBeTruthy());

    fireEvent.click(screen.getByLabelText('browser'));
    fireEvent.click(screen.getByText('بحث'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(2));
    const params = new URLSearchParams(String((reqMock.mock.calls[1] as unknown[])[0]).split('?')[1]);
    expect(params.getAll('source')).toEqual(['browser']);
  });

  it('a null status_code renders blank, never 0', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText(BROWSER.message)).toBeTruthy());
    expect(screen.queryByText(/HTTP 0/)).toBeNull();
    expect(screen.queryByText(/HTTP/)).toBeNull();
  });

  it('the detail blob is rendered generically, and only when asked for', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText(POD.message)).toBeTruthy());
    expect(screen.queryByText(/ConnectionRefusedError/)).toBeNull();

    fireEvent.click(screen.getByText('التفاصيل'));
    // A component that knew these keys would render nothing the day a new emitter arrives.
    await waitFor(() => expect(screen.getByText(/ConnectionRefusedError/)).toBeTruthy());
    expect(screen.getByText(/base-services/)).toBeTruthy();
  });

  it('empty says «no errors with these filters», never «everything is fine»', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أخطاء بهذي الفلاتر.')).toBeTruthy());
  });

  it('a failed read says so — never an empty list that reads as a healthy platform', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockRejectedValue(new Error('down'));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText('تعذّرت قراءة سجل الأخطاء.')).toBeTruthy());
  });

  it('without the action, the screen says so rather than quietly rendering nothing', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    reqMock = vi.fn();

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText('سجل الأخطاء ليس ضمن صلاحياتك.')).toBeTruthy());
    expect(reqMock).not.toHaveBeenCalled();
  });

  it('copies a row, and copies all filtered rows, in the same format', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText('نسخ').length).toBe(2));

    fireEvent.click(screen.getAllByText('نسخ')[0]);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(signalToText(BROWSER)));

    fireEvent.click(screen.getByText('نسخ الكل'));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
    const bulk = String(writeText.mock.calls[1][0]);
    // A row copied on its own and the same row inside a bulk copy must be byte-identical, or a
    // support thread and a ticket look like two different incidents.
    expect(bulk).toContain(signalToText(POD));
    expect(bulk).toContain(signalToText(BROWSER));
  });
});

describe('signalToText', () => {
  it('omits a null status and an empty request id rather than printing them empty', () => {
    const text = signalToText(BROWSER);
    expect(text).not.toContain('status:');
    expect(text).not.toContain('request_id:');
    expect(text).toContain(BROWSER.message);
  });

  it('includes them when they exist', () => {
    const text = signalToText(POD);
    expect(text).toContain('status: 500');
    expect(text).toContain('request_id: req-abc');
  });
});
