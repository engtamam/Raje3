/**
 * ServicesImportDrawer — proven at the level that matters: parsing a real CSV, catching a
 * duplicate name within the file, telling apart "جديد" from "تحديث" against the services already
 * on screen, and refusing to enable Import while any row is still wrong.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ServicesImportDrawer } from './ServicesImportDrawer';
import type { Catalog } from '../catalog';
import type { Session } from '../session';

const SESSION = { tenant: 't1', operator: 'op1', operatorName: 'Op', token: 'tok-1' } as Session;

const CATALOG: Catalog = {
  services: [{ service: 'operations', actions: [
    { id: 'operations.bulk_import_services', label: 'استيراد', method: 'POST',
     path: '/api/v1/staff/services/bulk_import', capability: 'operations.manage_services' },
  ] }],
  unreachable: [],
};

let callMock: ReturnType<typeof vi.fn>;

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return { ...real, call: (...args: unknown[]) => callMock(...args) };
});

afterEach(() => vi.clearAllMocks());

// jsdom's own File has no working `.text()` in this toolchain's version — the component only
// ever calls `.text()` on what it gets from the input, so a duck-typed object serves identically
// without depending on jsdom's File implementation catching up.
function selectFile(text: string) {
  const input = document.querySelector('input[type="file"]') as HTMLInputElement;
  const file = { name: 'services.csv', text: () => Promise.resolve(text) };
  Object.defineProperty(input, 'files', { value: [file] });
  fireEvent.change(input);
}

describe('ServicesImportDrawer', () => {
  it('parses a real file and shows جديد for a name not already on screen', async () => {
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG} existing={[]} open
                                onClose={() => {}} onImported={() => {}} />);
    selectFile('name,price\nقص شعر,50');
    await waitFor(() => expect(screen.getByText('قص شعر')).toBeTruthy());
    expect(screen.getByText('جديد')).toBeTruthy();
  });

  it('a name that matches an existing active service shows تحديث, not جديد', async () => {
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG}
                                existing={[{ name: 'قص شعر', active: true }]} open
                                onClose={() => {}} onImported={() => {}} />);
    selectFile('name,price\nقص شعر,60');
    await waitFor(() => expect(screen.getByText('تحديث')).toBeTruthy());
  });

  it('a stopped service reappearing shows إعادة تفعيل', async () => {
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG}
                                existing={[{ name: 'قص شعر', active: false }]} open
                                onClose={() => {}} onImported={() => {}} />);
    selectFile('name\nقص شعر');
    await waitFor(() => expect(screen.getByText('إعادة تفعيل')).toBeTruthy());
  });

  it('a name repeated twice in the file blocks import and marks BOTH rows', async () => {
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG} existing={[]} open
                                onClose={() => {}} onImported={() => {}} />);
    selectFile('name\nقص شعر\nقص شعر');
    await waitFor(() => expect(screen.getAllByText(/الاسم مكرر/).length).toBe(2));
    expect(screen.getByText(/2 صف فيه خطأ/)).toBeTruthy();
    const importBtn = screen.getByText(/استيراد 2 صف/).closest('button') as HTMLButtonElement;
    expect(importBtn.disabled).toBe(true);
  });

  it('an empty name is refused, and the row explains why', async () => {
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG} existing={[]} open
                                onClose={() => {}} onImported={() => {}} />);
    selectFile('name,price\n,50');
    await waitFor(() => expect(screen.getByText('الاسم فاضي.')).toBeTruthy());
  });

  it('a clean file imports through the real action, halalas on the wire', async () => {
    callMock = vi.fn().mockResolvedValue({ created: 1, updated: 0, reactivated: 0, deactivated: 0 });
    const onImported = vi.fn();
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG} existing={[]} open
                                onClose={() => {}} onImported={onImported} />);
    selectFile('name,price\nقص شعر,50');
    await waitFor(() => expect(screen.getByText('جديد')).toBeTruthy());

    fireEvent.click(screen.getByText(/استيراد 1 صف/));

    await waitFor(() => expect(callMock).toHaveBeenCalledWith(SESSION,
      expect.objectContaining({ id: 'operations.bulk_import_services' }),
      expect.objectContaining({
        rows: [{ name: 'قص شعر', price_minor: 5000, duration_minutes: 0, cycle_days: 0, external_id: '' }],
        deactivate_missing: false,
      })));
    await waitFor(() => expect(onImported).toHaveBeenCalled());
    expect(screen.getByText(/تم الاستيراد/)).toBeTruthy();
  });

  it('an active service missing from the file offers the opt-in deactivate toggle, off by default', async () => {
    render(<ServicesImportDrawer session={SESSION} catalog={CATALOG}
                                existing={[{ name: 'قص شعر', active: true }, { name: 'غسيل', active: true }]}
                                open onClose={() => {}} onImported={() => {}} />);
    selectFile('name\nقص شعر');
    await waitFor(() => expect(screen.getByText(/1 خدمة مفعّلة/)).toBeTruthy());
    expect(screen.getByText('غسيل')).toBeTruthy();
    expect(screen.getByRole('switch').getAttribute('aria-checked')).toBe('false');
  });
});
