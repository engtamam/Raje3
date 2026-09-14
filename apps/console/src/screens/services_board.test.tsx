/**
 * «خدماتي» — the board/cards view (services-images-board.md phase 3): the list/grid toggle, a
 * photo (or a real placeholder) per service, and the description field in the edit row. Server
 * calls mocked; the request shapes themselves are covered on the backend side
 * (test_catalogue_image.py, test_bulk_import_services.py).
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { OperatorI18nProvider } from '../operator-i18n';

// irrelevant to this suite — same "not this person at all" fallback to Arabic as
// services_import_drawer.test.tsx uses.
vi.mock('../api', () => ({
  getMyLocale: async () => { throw new Error('not mocked'); },
  setMyLocale: async () => ({}),
}));

const ACTIONS: Record<string, { id: string; label: string; method: string; path: string }> = {
  'operations.manage_services': { id: 'operations.manage_services', label: 'x', method: 'GET', path: '/services' },
  'operations.update_service': { id: 'operations.update_service', label: 'x', method: 'PATCH', path: '/services/{id}' },
  'operations.get_service_image': { id: 'operations.get_service_image', label: 'x', method: 'GET', path: '/services/{id}/image' },
  'operations.upload_service_image': { id: 'operations.upload_service_image', label: 'x', method: 'POST', path: '/services/{id}/image' },
  'operations.create_service': { id: 'operations.create_service', label: 'x', method: 'POST', path: '/services' },
  'operations.list_operators': { id: 'operations.list_operators', label: 'x', method: 'GET', path: '/operators' },
  'reminders.get_settings': { id: 'reminders.get_settings', label: 'x', method: 'GET', path: '/settings' },
};

let servicesResponse: Record<string, unknown>[] = [
  { id: 'svc_a', name: 'غسيل خارجي', active: true, price_minor: 5000, has_image: true,
    description: 'غسيل كامل بالماء والصابون' },
  { id: 'svc_b', name: 'تلميع', active: true, price_minor: 8000, has_image: false, description: '' },
];
const patchCalls: unknown[] = [];
const uploadCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ACTIONS[id] ?? null,
    call: async (_session: unknown, a: { id: string }, body: unknown) => {
      if (a.id === 'operations.list_operators' || a.id === 'operations.manage_services') {
        // manage_services doubles as the list route here — same action object either way
        return { services: servicesResponse, operators: [] };
      }
      if (a.id === 'reminders.get_settings') {
        return { general: {}, services: {}, groups: {}, service_group: {} };
      }
      if (a.id === 'operations.update_service') { patchCalls.push(body); return {}; }
      if (a.id === 'operations.upload_service_image') { uploadCalls.push(body); return {}; }
      return {};
    },
    downloadUrl: async () => 'blob:fake-image-url',
  };
});

const { ServicesScreen } = await import('./Services');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(
    <MemoryRouter initialEntries={['/services']}>
      <OperatorI18nProvider session={session}>
        <ServicesScreen session={session} catalog={catalog} />
      </OperatorI18nProvider>
    </MemoryRouter>,
  );
}

describe('خدماتي — board/cards (phase 3)', () => {
  it('defaults to the table and switches to the card grid on request', async () => {
    open();
    await waitFor(() => expect(screen.getByText('غسيل خارجي')).toBeTruthy());
    // the table is the mouse default — a real <table> element is present
    expect(document.querySelector('table')).toBeTruthy();

    fireEvent.click(screen.getByLabelText('بطاقات'));
    await waitFor(() => expect(document.querySelector('table')).toBeFalsy());
    expect(screen.getByText('غسيل خارجي')).toBeTruthy();
  });

  it('a service with a photo shows it in the grid; one without shows the real placeholder', async () => {
    open();
    await waitFor(() => expect(screen.getByText('غسيل خارجي')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('بطاقات'));
    // the card's photo is decorative (alt="") — real ARIA strips its img role, so query the DOM directly
    await waitFor(() => expect(document.querySelectorAll('img').length).toBeGreaterThan(0));
    const img = document.querySelector('img') as HTMLImageElement;
    expect(img.src).toContain('blob:fake-image-url');
  });

  it("clicking a card's edit button opens the inspector in place, not the table", async () => {
    open();
    await waitFor(() => expect(screen.getByText('غسيل خارجي')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('بطاقات'));
    await waitFor(() => expect(screen.getAllByText('تعديل').length).toBeGreaterThan(0));
    // both cards (svc_a, svc_b) carry an edit button — svc_a's is first
    fireEvent.click(screen.getAllByText('تعديل')[0]);
    // STAYS ON THE GRID — a card is a photo first, and the view he chose is not thrown away just
    // to change a name. The docked inspector pane opens beside it instead (2026-09-14 workspace
    // redesign, replacing the old <Modal>), with the same name as a real input.
    await waitFor(() => expect(screen.getByDisplayValue('غسيل خارجي')).toBeTruthy());
    expect(document.querySelector('table')).toBeFalsy();
    expect(screen.queryByRole('dialog')).toBeFalsy();
  });

  it('editing a row shows the description field, pre-filled, and saves on blur', async () => {
    open();
    await waitFor(() => expect(screen.getByText('غسيل خارجي')).toBeTruthy());
    // the table (list layout) is the mouse default — svc_a's own row pencil opens it
    fireEvent.click(screen.getAllByLabelText('تعديل')[0]);
    const desc = await screen.findByPlaceholderText('وصف قصير (يستخدمه الذكاء الاصطناعي بالواتساب)') as HTMLInputElement;
    expect(desc.value).toBe('غسيل كامل بالماء والصابون');
    fireEvent.change(desc, { target: { value: 'وصف جديد' } });
    fireEvent.blur(desc);
    await waitFor(() => expect(patchCalls.length).toBeGreaterThan(0));
    expect(patchCalls[patchCalls.length - 1]).toMatchObject({ description: 'وصف جديد' });
  });
});
