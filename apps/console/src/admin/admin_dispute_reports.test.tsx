/**
 * تقارير الدفاع النزاعي — الاختبارات تتأكد أن التوليد لا يصير بدون رقم جوال سعودي صحيح وسيناريو
 * مختار، والملف الراجع من الخادم يُنزَّل حقيقة (Blob)، لا JSON، والفشل يُعرض بوضوح.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminDisputeReports } from './AdminDisputeReports';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'insights', actions: [
      { id: 'insights.dispute_report', label: 'x', method: 'POST' as const,
       path: '/api/v1/insights/dispute-report', capability: 'platform.compliance' },
    ] },
  ],
  unreachable: [],
};

let fetchCatalogMock: ReturnType<typeof vi.fn>;
let fetchMock: ReturnType<typeof vi.fn>;

vi.mock('./catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('./catalog')>();
  return { ...real, fetchCatalog: (...args: unknown[]) => fetchCatalogMock(...args) };
});

afterEach(() => { vi.clearAllMocks(); vi.unstubAllGlobals(); });

describe('AdminDisputeReports', () => {
  it('the generate button stays disabled until a valid Saudi phone AND a scenario are both set', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    render(<AdminDisputeReports session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('رقم جوال مالك المنشأة')).toBeTruthy());

    const button = screen.getByText('توليد التقرير') as HTMLButtonElement;
    expect(button.disabled).toBe(true);

    fireEvent.change(screen.getByLabelText('رقم جوال مالك المنشأة'), { target: { value: '0501234567' } });
    expect(button.disabled).toBe(true); // still no scenario chosen

    fireEvent.click(screen.getByText('فقدان بيانات'));
    expect(button.disabled).toBe(false);
  });

  it('a short or non-Saudi number keeps the button disabled even with a scenario chosen', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    render(<AdminDisputeReports session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('رقم جوال مالك المنشأة')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('رقم جوال مالك المنشأة'), { target: { value: '0912345' } });
    fireEvent.click(screen.getByText('خطأ فوترة'));
    expect((screen.getByText('توليد التقرير') as HTMLButtonElement).disabled).toBe(true);
  });

  it('generating fetches the action path with phone/scenario/format and downloads the returned file', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    const blob = new Blob(['fake docx bytes']);
    fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: (k: string) => (k === 'content-disposition' ? 'attachment; filename="dispute_data_loss_tnt_1.docx"' : null) },
      blob: async () => blob,
    });
    vi.stubGlobal('fetch', fetchMock);
    const createObjectURL = vi.fn().mockReturnValue('blob:fake');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });

    render(<AdminDisputeReports session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('رقم جوال مالك المنشأة')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('رقم جوال مالك المنشأة'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('فقدان بيانات'));
    fireEvent.click(screen.getByText('توليد التقرير'));

    await waitFor(() => expect(screen.getByText('الملف جاهز')).toBeTruthy());
    expect(fetchMock).toHaveBeenCalledWith('/api/v1/insights/dispute-report', expect.objectContaining({
      method: 'POST',
      headers: expect.objectContaining({ Authorization: 'Bearer tok-1' }),
      body: JSON.stringify({ phone: '0501234567', scenario: 'data_loss', file_format: 'docx' }),
    }));
    expect(screen.getByText('dispute_data_loss_tnt_1.docx')).toBeTruthy();

    fireEvent.click(screen.getByText('تنزيل الملف'));
    expect(createObjectURL).toHaveBeenCalledWith(blob);
  });

  it('a refused generation shows the server sentence, not a raw error', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    fetchMock = vi.fn().mockResolvedValue({
      ok: false,
      json: async () => ({ reason: 'لا توجد منشأة مسجَّلة بهذا الرقم كمالك.' }),
    });
    vi.stubGlobal('fetch', fetchMock);

    render(<AdminDisputeReports session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('رقم جوال مالك المنشأة')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('رقم جوال مالك المنشأة'), { target: { value: '0501234567' } });
    fireEvent.click(screen.getByText('خطأ فوترة'));
    fireEvent.click(screen.getByText('توليد التقرير'));

    await waitFor(() => expect(screen.getByText('لا توجد منشأة مسجَّلة بهذا الرقم كمالك.')).toBeTruthy());
  });

  it('no capability, no tab that quietly does nothing — the screen says so', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminDisputeReports session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });
});
