/**
 * محرر المستندات القانونية — الاختبارات تتأكد أن النشر لا يصير إلا بعد حفظ مسوّدة وتأكيد صريح،
 * وأن المحتوى المرسَل بالشكل اللي BlockRenderer.tsx يفهمه فعلاً، وأن غياب الصلاحية يُقال صراحة.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminLegal } from './AdminLegal';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'compliance-service', actions: [
      { id: 'compliance.legal_draft', label: 'x', method: 'PUT' as const,
       path: '/api/v1/compliance/legal/{doc_id}/versions/{version}', capability: 'platform.compliance' },
      { id: 'compliance.legal_publish', label: 'x', method: 'POST' as const,
       path: '/api/v1/compliance/legal/{doc_id}/versions/{version}/publish',
       capability: 'platform.compliance', confirm: true },
    ] },
  ],
  unreachable: [],
};

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

describe('AdminLegal', () => {
  it('drafts with the Block shape BlockRenderer.tsx actually reads, then requires a separate confirm to publish', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({ doc_id: 'privacy-policy', version: '1.1', status: 'draft' });

    render(<AdminLegal session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText(/معرّف المستند/)).toBeTruthy());

    fireEvent.change(screen.getByLabelText(/معرّف المستند/), { target: { value: 'privacy-policy' } });
    fireEvent.change(screen.getByLabelText(/رقم النسخة/), { target: { value: '1.1' } });
    fireEvent.change(screen.getByLabelText('النص (عربي، Markdown)'), { target: { value: '## عنوان\nفقرة كاملة.' } });

    fireEvent.click(screen.getByText('حفظ كمسوّدة'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/compliance/legal/privacy-policy/versions/1.1', 'PUT',
      {
        content: {
          title: { ar: '', en: '' },
          blocks: [{ type: 'text', data: { md_ar: '## عنوان\nفقرة كاملة.', md_en: '' } }],
        },
        requires_acceptance: true,
      },
      'tok-1',
    ));
    await waitFor(() => expect(screen.getByText(/حُفظت المسوّدة/)).toBeTruthy());

    // PUBLISH IS STILL GATED — drafting alone must never call the publish route.
    expect(reqMock).not.toHaveBeenCalledWith(
      '/api/v1/compliance/legal/privacy-policy/versions/1.1/publish', 'POST', undefined, 'tok-1',
    );
    const publishButton = screen.getByText('نشر') as HTMLButtonElement;
    expect(publishButton.disabled).toBe(false);
    fireEvent.click(publishButton);

    await waitFor(() => expect(screen.getByText(/نشر "privacy-policy" نسخة 1.1؟/)).toBeTruthy());
    fireEvent.click(screen.getByText('تأكيد'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/compliance/legal/privacy-policy/versions/1.1/publish', 'POST', undefined, 'tok-1',
    ));
    await waitFor(() => expect(screen.getByText(/^نُشرت\./)).toBeTruthy());
  });

  it('publish stays disabled until a draft actually saved', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    render(<AdminLegal session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText(/معرّف المستند/)).toBeTruthy());

    fireEvent.change(screen.getByLabelText(/معرّف المستند/), { target: { value: 'terms' } });
    fireEvent.change(screen.getByLabelText(/رقم النسخة/), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('النص (عربي، Markdown)'), { target: { value: 'نص' } });

    expect((screen.getByText('نشر') as HTMLButtonElement).disabled).toBe(true);
  });

  it('renders a live preview from the same Markdown renderer legal docs actually use', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    render(<AdminLegal session={SESSION} />);
    await waitFor(() => expect(screen.getByLabelText('النص (عربي، Markdown)')).toBeTruthy());

    fireEvent.change(screen.getByLabelText('النص (عربي، Markdown)'), { target: { value: '## عنوان المعاينة' } });
    await waitFor(() => expect(screen.getByRole('heading', { name: 'عنوان المعاينة' })).toBeTruthy());
  });

  it('no capability, no tab that quietly does nothing — the screen says so', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminLegal session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });
});
