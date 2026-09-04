/**
 * المستندات القانونية — الاختبارات تتأكد أن القائمة تعرض ما موجود فعلاً (منشور أو مسوّدة معلّقة)،
 * أن فتح نوع موجود يجيب سجل نسخه، أن "نوع جديد" يفتح نموذجاً فاضياً بمعرّف حر، أن النشر لا يصير
 * إلا بعد حفظ مسوّدة وتأكيد صريح، وأن المحتوى المرسَل بالشكل اللي BlockRenderer.tsx يفهمه فعلاً،
 * وأن غياب الصلاحية يُقال صراحة.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminLegal } from './AdminLegal';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'compliance-service', actions: [
      { id: 'compliance.legal_list', label: 'x', method: 'GET' as const,
       path: '/api/v1/compliance/legal', capability: 'platform.compliance' },
      { id: 'compliance.legal_history', label: 'x', method: 'GET' as const,
       path: '/api/v1/compliance/legal/{doc_id}/history', capability: 'platform.compliance' },
      { id: 'compliance.legal_draft', label: 'x', method: 'PUT' as const,
       path: '/api/v1/compliance/legal/{doc_id}/versions/{version}', capability: 'platform.compliance' },
      { id: 'compliance.legal_publish', label: 'x', method: 'POST' as const,
       path: '/api/v1/compliance/legal/{doc_id}/versions/{version}/publish',
       capability: 'platform.compliance', confirm: true },
    ] },
  ],
  unreachable: [],
};

const DOCS = [
  { doc_id: 'privacy-policy', version: '1.0', status: 'published' as const, requires_acceptance: true },
  { doc_id: 'brand-new-type', version: null, status: 'draft' as const, requires_acceptance: false },
];

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

function stubReq() {
  reqMock = vi.fn((path: string) => {
    if (path === '/api/v1/compliance/legal') return Promise.resolve({ documents: DOCS });
    if (path.endsWith('/history')) return Promise.resolve({ versions: [
      { version: '1.0', status: 'published', published_at: 1700000000, requires_acceptance: true },
    ] });
    return Promise.resolve({ doc_id: 'privacy-policy', version: '1.1', status: 'draft' });
  });
}

describe('AdminLegal', () => {
  it('lists what already exists — published AND draft-only types, not a blank form', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    stubReq();
    render(<AdminLegal session={SESSION} />);

    await waitFor(() => expect(screen.getByText('privacy-policy')).toBeTruthy());
    expect(screen.getByText(/منشور — نسخة 1.0/)).toBeTruthy();
    expect(screen.getByText('brand-new-type')).toBeTruthy();
    expect(screen.getByText(/مسوّدة، لم يُنشر/)).toBeTruthy();
  });

  it('opening an existing type fetches and shows its version history', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    stubReq();
    render(<AdminLegal session={SESSION} />);

    await waitFor(() => expect(screen.getByText('privacy-policy')).toBeTruthy());
    fireEvent.click(screen.getByText('privacy-policy'));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/compliance/legal/privacy-policy/history', 'GET', undefined, 'tok-1',
    ));
    await waitFor(() => expect(screen.getByLabelText(/معرّف المستند/)).toBeTruthy());
    expect((screen.getByLabelText(/معرّف المستند/) as HTMLInputElement).value).toBe('privacy-policy');
    expect((screen.getByLabelText(/معرّف المستند/) as HTMLInputElement).disabled).toBe(true);
  });

  it('"نوع مستند جديد" opens an empty form with a free doc_id, no history call', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    stubReq();
    render(<AdminLegal session={SESSION} />);

    await waitFor(() => expect(screen.getByText('نوع مستند جديد')).toBeTruthy());
    fireEvent.click(screen.getByText('نوع مستند جديد'));

    const docIdField = screen.getByLabelText(/معرّف المستند/) as HTMLInputElement;
    expect(docIdField.value).toBe('');
    expect(docIdField.disabled).toBe(false);
    fireEvent.change(docIdField, { target: { value: 'refund-policy' } });
    fireEvent.change(screen.getByLabelText(/رقم النسخة/), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('النص (عربي، Markdown)'), { target: { value: 'نص' } });
    expect((screen.getByText('حفظ كمسوّدة') as HTMLButtonElement).disabled).toBe(false);
  });

  it('drafts with the Block shape BlockRenderer.tsx actually reads, then requires a separate confirm to publish', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    stubReq();

    render(<AdminLegal session={SESSION} />);
    await waitFor(() => expect(screen.getByText('privacy-policy')).toBeTruthy());
    fireEvent.click(screen.getByText('privacy-policy'));
    await waitFor(() => expect(screen.getByLabelText(/رقم النسخة/)).toBeTruthy());

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
    stubReq();
    render(<AdminLegal session={SESSION} />);

    await waitFor(() => expect(screen.getByText('نوع مستند جديد')).toBeTruthy());
    fireEvent.click(screen.getByText('نوع مستند جديد'));
    fireEvent.change(screen.getByLabelText(/معرّف المستند/), { target: { value: 'terms' } });
    fireEvent.change(screen.getByLabelText(/رقم النسخة/), { target: { value: '1' } });
    fireEvent.change(screen.getByLabelText('النص (عربي، Markdown)'), { target: { value: 'نص' } });

    expect((screen.getByText('نشر') as HTMLButtonElement).disabled).toBe(true);
  });

  it('renders a live preview from the same Markdown renderer legal docs actually use', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    stubReq();
    render(<AdminLegal session={SESSION} />);

    await waitFor(() => expect(screen.getByText('نوع مستند جديد')).toBeTruthy());
    fireEvent.click(screen.getByText('نوع مستند جديد'));
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
