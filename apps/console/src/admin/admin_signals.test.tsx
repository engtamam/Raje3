/**
 * سجل الأخطاء — تثبّت: لا فلتر عند أول تحميل، الفلاتر تُبنى من البيانات لا من قائمة مكتوبة هنا،
 * الخدمة والمدة اختيار من قائمة يعيد البحث فوراً، نسخ كل صف نصاً وJSON كاملاً، «لا نتائج» ليست
 * «كل شيء سليم»، والبحث بعميل يصفّي الجدول على منشأته وهويّته المستعارة.
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
    { service: 'operations', actions: [
      { id: 'operations.customer_by_phone', label: 'ابحث عن عميل برقم جواله', method: 'GET' as const,
       path: '/api/v1/platform/customers/by-phone', capability: 'platform.operations' },
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
  it('shows a pod error and a browser error in ONE table', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));

    render(<AdminSignals session={SESSION} />);
    // `getAllByText` throughout — rj-ui's own Table renders BOTH a desktop <table> and a mobile
    // card list at once (CSS-hidden either way, both real DOM nodes jsdom does not hide), so every
    // row's content legitimately appears twice. Same reason each value also appears once more as
    // its own filter checkbox — the point of the filters being built from the data.
    await waitFor(() => expect(screen.getAllByText(POD.message).length).toBeGreaterThan(0));
    expect(screen.getAllByText(BROWSER.message).length).toBeGreaterThan(0);
    expect(screen.getAllByText('server_log').length).toBeGreaterThan(0);
    expect(screen.getAllByText('browser').length).toBeGreaterThan(0);
    expect(screen.getAllByText('loyalty').length).toBeGreaterThan(0);
    expect(screen.getAllByText('console').length).toBeGreaterThan(0);
  });

  it('the first load applies NO severity/source filter — every error, visibly', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalled());
    const url = String((reqMock.mock.calls[0] as unknown[])[0]);
    const params = new URLSearchParams(url.split('?')[1]);
    expect(params.getAll('severity')).toEqual([]);
    expect(params.getAll('source')).toEqual([]);
    expect(params.get('service')).toBeNull();
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
    // No severity is pre-checked any more — an operator opening the screen sees everything first.
    expect((screen.getByLabelText('error') as HTMLInputElement).checked).toBe(false);
    expect((screen.getByLabelText('warning') as HTMLInputElement).checked).toBe(false);
  });

  it('ticking a source sends it as a repeated query param', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('browser')).toBeTruthy());

    fireEvent.click(screen.getByLabelText('browser'));
    // Two «بحث» buttons on this screen — the shared customer-lookup box's own, and this filter
    // form's — the filter one is the LAST rendered (the lookup box sits above the form in the DOM).
    const searchButtons = screen.getAllByText('بحث');
    fireEvent.click(searchButtons[searchButtons.length - 1]);

    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(2));
    const params = new URLSearchParams(String((reqMock.mock.calls[1] as unknown[])[0]).split('?')[1]);
    expect(params.getAll('source')).toEqual(['browser']);
  });

  it('picking a service from the select re-searches immediately, no «بحث» press needed', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByDisplayValue('كل الخدمات'), { target: { value: 'loyalty' } });

    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(2));
    const params = new URLSearchParams(String((reqMock.mock.calls[1] as unknown[])[0]).split('?')[1]);
    expect(params.get('service')).toBe('loyalty');
  });

  it('picking a duration preset re-searches immediately with the matching window', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([POD]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByDisplayValue('آخر 24 ساعة'), { target: { value: '' } });

    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(2));
    const params = new URLSearchParams(String((reqMock.mock.calls[1] as unknown[])[0]).split('?')[1]);
    // «بلا حد زمني» sends no since= at all.
    expect(params.get('since')).toBeNull();
  });

  it('a null status_code renders no HTTP badge, never HTTP 0', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText(BROWSER.message).length).toBeGreaterThan(0));
    expect(screen.queryByText(/HTTP 0/)).toBeNull();
    expect(screen.queryByText(/HTTP/)).toBeNull();
  });

  it('copies one row as text, and the same row as full JSON including detail/context', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([POD]));
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText(POD.message).length).toBeGreaterThan(0));

    // getAllBy — the desktop/mobile dual render means every row action exists twice too; either
    // copy of the SAME row's button produces identical output, so the first is enough to assert.
    fireEvent.click(screen.getAllByLabelText('نسخ كنص')[0]);
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(signalToText(POD)));

    fireEvent.click(screen.getAllByLabelText('نسخ JSON كامل')[0]);
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(2));
    const json = JSON.parse(String(writeText.mock.calls[1][0]));
    expect(json.id).toBe(POD.id);
    expect(json.detail.exception).toBe('ConnectionRefusedError');
    expect(json.context.namespace).toBe('base-services');
  });

  it('empty says «no errors with these filters», never «everything is fine»', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([]));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText('لا أخطاء بهذي الفلاتر')).toBeTruthy());
  });

  it('a failed read says so — never an empty list that reads as a healthy platform', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockRejectedValue(new Error('down'));

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText('تعذّرت قراءة سجل الأخطاء')).toBeTruthy());
  });

  it('without the action, the screen says so rather than quietly rendering nothing', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    reqMock = vi.fn();

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getByText('سجل الأخطاء ليس ضمن صلاحياتك.')).toBeTruthy());
    expect(reqMock).not.toHaveBeenCalled();
  });

  it('copies all filtered rows in one text block, in the same per-row format', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue(page([BROWSER, POD]));
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(screen.getAllByText(POD.message).length).toBeGreaterThan(0));

    fireEvent.click(screen.getByText('نسخ الكل نصاً'));
    await waitFor(() => expect(writeText).toHaveBeenCalledTimes(1));
    const bulk = String(writeText.mock.calls[0][0]);
    expect(bulk).toContain(signalToText(POD));
    expect(bulk).toContain(signalToText(BROWSER));
  });

  it('searching a customer filters the table to their tenant + pseudonym', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce(page([BROWSER, POD]))   // first, unfiltered load
      .mockResolvedValueOnce({
        customer: { id: 'cus_1', tenant: 'tnt_x', phone: '0501234567', name: 'أحمد',
                   visit_count: 1, last_visit: 0, subject_ref: 'sref_abc' },
      })
      .mockResolvedValueOnce(page([POD]));   // reload, now customer-filtered

    render(<AdminSignals session={SESSION} />);
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByPlaceholderText('tnt_...'), { target: { value: 'tnt_x' } });
    fireEvent.change(screen.getByPlaceholderText('05xxxxxxxx'), { target: { value: '0501234567' } });
    // Two «بحث» buttons on this screen — the customer-lookup box's own is the FIRST rendered.
    fireEvent.click(screen.getAllByText('بحث')[0]);

    await waitFor(() => expect(screen.getByText('أحمد')).toBeTruthy());
    await waitFor(() => expect(reqMock).toHaveBeenCalledTimes(3));
    const params = new URLSearchParams(String((reqMock.mock.calls[2] as unknown[])[0]).split('?')[1]);
    expect(params.get('tenant')).toBe('tnt_x');
    expect(params.get('subject_ref')).toBe('sref_abc');
    expect(screen.getByText('مصفّى على عميل واحد.')).toBeTruthy();
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
