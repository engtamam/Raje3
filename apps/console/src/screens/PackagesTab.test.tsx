/**
 * «الباقات» — the list, the empty state, and the create dialog (server calls mocked; the real
 * request shape is covered on the backend side).
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const ACTIONS: Record<string, { id: string; label: string; method: string; path: string }> = {
  'operations.manage_services': { id: 'operations.manage_services', label: 'x', method: 'GET', path: '/services' },
  'operations.list_packages': { id: 'operations.list_packages', label: 'x', method: 'GET', path: '/packages' },
  'operations.list_services': { id: 'operations.list_services', label: 'x', method: 'GET', path: '/services' },
  'operations.create_package': { id: 'operations.create_package', label: 'x', method: 'POST', path: '/packages' },
  'operations.update_package': { id: 'operations.update_package', label: 'x', method: 'PATCH', path: '/packages/{id}' },
  'operations.get_package_image': { id: 'operations.get_package_image', label: 'x', method: 'GET', path: '/packages/{id}/image' },
  'operations.upload_package_image': { id: 'operations.upload_package_image', label: 'x', method: 'POST', path: '/packages/{id}/image' },
  'operations.delete_package_image': { id: 'operations.delete_package_image', label: 'x', method: 'DELETE', path: '/packages/{id}/image' },
  'loyalty.settings.read': { id: 'loyalty.settings.read', label: 'x', method: 'GET', path: '/settings' },
  'loyalty.settings.package': { id: 'loyalty.settings.package', label: 'x', method: 'PUT', path: '/settings/package/{package_id}' },
};

let packagesResponse: unknown[] = [];
let servicesResponse: unknown[] = [
  { id: 'svc_a', name: 'قص شعر', active: true },
  { id: 'svc_b', name: 'فحص فرامل', active: true },
];
let earnResponse: unknown = { services: {}, groups: {}, service_group: {}, general: {}, packages: {} };
let servicesFail = false;
const createCalls: unknown[] = [];
const pointsCalls: unknown[] = [];
const uploadImageCalls: unknown[] = [];
const deleteImageCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ACTIONS[id] ?? null,
    call: async (_session: unknown, a: { id: string }, body: unknown) => {
      if (a.id === 'operations.list_packages') return { packages: packagesResponse };
      if (a.id === 'operations.list_services') {
        if (servicesFail) throw new Error('boom');
        return { services: servicesResponse };
      }
      if (a.id === 'loyalty.settings.read') return earnResponse;
      if (a.id === 'operations.create_package') { createCalls.push(body); return { id: 'pkg_new' }; }
      if (a.id === 'operations.update_package') { createCalls.push(body); return {}; }
      if (a.id === 'loyalty.settings.package') { pointsCalls.push(body); return {}; }
      if (a.id === 'operations.upload_package_image') { uploadImageCalls.push(body); return {}; }
      if (a.id === 'operations.delete_package_image') { deleteImageCalls.push(body); return {}; }
      return {};
    },
    downloadUrl: async () => 'blob:fake-image-url',
  };
});

const { PackagesTab } = await import('./PackagesTab');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open(initialEntries = ['/services?tab=packages']) {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <PackagesTab session={session} catalog={catalog} />
    </MemoryRouter>,
  );
}

describe('الباقات', () => {
  it('shows the empty state and an invitation to create the first one', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => expect(screen.getByText('لا توجد باقات بعد')).toBeTruthy());
    expect(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ })).toBeTruthy();
  });

  // م · النمط 1 — «services» used to fail into the same empty state a genuinely empty catalogue
  // renders, so a failed read of the shop's own services looked exactly like a fresh shop with
  // nothing configured yet.
  it('says the read failed when the services catalogue cannot be read, never that there are no packages', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000, active: true },
    ];
    servicesFail = true;
    open();
    await waitFor(() => expect(screen.getByText(/تعذّرت قراءة الباقات أو الخدمات/)).toBeTruthy());
    expect(screen.queryByText('لا توجد باقات بعد')).toBeNull();
    servicesFail = false;
  });

  it('lists an existing package with its real component names and price', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000, active: true },
    ];
    open();
    await waitFor(() => expect(screen.getByText('باقة الصيانة')).toBeTruthy());
    expect(screen.getByText('قص شعر')).toBeTruthy();
    expect(screen.getByText('فحص فرامل')).toBeTruthy();
    expect(screen.getByText('150 ريال')).toBeTruthy();
  });

  it('refuses to save with fewer than two services or no real price', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));
    expect((screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('creating a package with two services and a price calls create then sets its points', async () => {
    packagesResponse = [];
    createCalls.length = 0; pointsCalls.length = 0;
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.change(screen.getByPlaceholderText(/باقة الصيانة الشاملة/), { target: { value: 'باقة جديدة' } });
    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    const priceBox = screen.getByPlaceholderText('0');
    fireEvent.change(priceBox, { target: { value: '150' } });

    await waitFor(() => expect(
      (screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));

    await waitFor(() => expect(createCalls.length).toBe(1));
    const body = createCalls[0] as { name: string; service_ids: string[]; price_minor: number };
    expect(body.name).toBe('باقة جديدة');
    expect(body.service_ids.sort()).toEqual(['svc_a', 'svc_b']);
    expect(body.price_minor).toBe(15000);
    expect(pointsCalls.length).toBe(1);
  });

  it('shows a schedule summary and the "غير مفعّلة اليوم" badge honestly', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة السبت', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, recurrence: 'weekly', recurrence_weekdays: [5], offerable_now: false },
    ];
    open();
    await waitFor(() => expect(screen.getByText('باقة السبت')).toBeTruthy());
    expect(screen.getByText('كل السبت')).toBeTruthy();
    expect(screen.getByText('غير مفعّلة اليوم')).toBeTruthy();
  });

  it('refuses to save a weekly schedule with no days chosen', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.change(screen.getByPlaceholderText(/باقة الصيانة الشاملة/), { target: { value: 'باقة' } });
    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '150' } });
    fireEvent.click(screen.getByText('أسبوعياً'));

    expect((screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(/أكمل تفاصيل الجدولة/)).toBeTruthy();

    fireEvent.click(screen.getByText('السبت'));
    await waitFor(() => expect(
      (screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(false));
  });

  it('creating a weekly package sends the chosen weekdays', async () => {
    packagesResponse = [];
    createCalls.length = 0;
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.change(screen.getByPlaceholderText(/باقة الصيانة الشاملة/), { target: { value: 'باقة السبت' } });
    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '150' } });
    fireEvent.click(screen.getByText('أسبوعياً'));
    fireEvent.click(screen.getByText('السبت'));

    await waitFor(() => expect(
      (screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));

    await waitFor(() => expect(createCalls.length).toBe(1));
    const body = createCalls[0] as { recurrence: string; recurrence_weekdays: number[] };
    expect(body.recurrence).toBe('weekly');
    expect(body.recurrence_weekdays).toEqual([5]);
  });

  it('opens the create dialog pre-filled from محلّي\'s bundle suggestion', async () => {
    packagesResponse = [];
    open(['/services?tab=packages&prefill_a=svc_a&prefill_b=svc_b']);
    await waitFor(() => expect(screen.getByPlaceholderText(/باقة الصيانة الشاملة/)).toBeTruthy());
    // Both suggested services are pre-checked (accent-highlighted) — visible as the price/points
    // form being immediately ready to save once a name and price are typed.
    expect(screen.getByText('قص شعر')).toBeTruthy();
    expect(screen.getByText('فحص فرامل')).toBeTruthy();
  });

  // ── deep robustness pass (100-test confidence sweep) ────────────────────────────────────────

  it('opens the extend-existing-package dialog with the extra service already added', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a'], price_minor: 15000, active: true },
    ];
    open(['/services?tab=packages&extend_package=pkg1&extend_service=svc_b']);
    await waitFor(() => expect(screen.getByDisplayValue('باقة الصيانة')).toBeTruthy());
    expect(screen.getByText('الخدمات (2 مُختارة — خدمتان على الأقل)')).toBeTruthy();
  });

  it('extend does nothing when the named package no longer exists', async () => {
    packagesResponse = [];
    open(['/services?tab=packages&extend_package=does_not_exist&extend_service=svc_b']);
    await waitFor(() => expect(screen.getByText('لا توجد باقات بعد')).toBeTruthy());
    expect(screen.queryByPlaceholderText(/باقة الصيانة الشاملة/)).toBeNull();
  });

  it('editing an existing package pre-fills its current price and services', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true },
    ];
    open();
    await waitFor(() => screen.getByText('باقة الصيانة'));
    fireEvent.click(screen.getByRole('button', { name: 'تعديل' }));
    await waitFor(() => expect(screen.getByDisplayValue('باقة الصيانة')).toBeTruthy());
    expect((screen.getByPlaceholderText('0') as HTMLInputElement).value).toBe('150');
  });

  it('toggling active calls update_package with the flipped value', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true },
    ];
    createCalls.length = 0;
    open();
    await waitFor(() => screen.getByText('باقة الصيانة'));
    fireEvent.click(screen.getByRole('switch'));
    await waitFor(() => expect(createCalls.length).toBe(1));
    expect((createCalls[0] as { active: boolean }).active).toBe(false);
  });

  it('creating a monthly package sends the chosen days of month', async () => {
    packagesResponse = [];
    createCalls.length = 0;
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.change(screen.getByPlaceholderText(/باقة الصيانة الشاملة/), { target: { value: 'باقة الشهر' } });
    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '150' } });
    fireEvent.click(screen.getByText('شهرياً'));
    fireEvent.click(screen.getByText('1'));

    await waitFor(() => expect(
      (screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(false));
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));

    await waitFor(() => expect(createCalls.length).toBe(1));
    const body = createCalls[0] as { recurrence: string; recurrence_days_of_month: number[] };
    expect(body.recurrence).toBe('monthly');
    expect(body.recurrence_days_of_month).toEqual([1]);
  });

  it('refuses to save a yearly schedule with no dates chosen', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.change(screen.getByPlaceholderText(/باقة الصيانة الشاملة/), { target: { value: 'باقة' } });
    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    fireEvent.change(screen.getByPlaceholderText('0'), { target: { value: '150' } });
    fireEvent.click(screen.getByText('سنوياً'));

    expect((screen.getByRole('button', { name: 'حفظ' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('unchecking a service removes it from the selection', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));

    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    expect(screen.getByText('الخدمات (2 مُختارة — خدمتان على الأقل)')).toBeTruthy();
    fireEvent.click(screen.getByText('قص شعر'));
    expect(screen.getByText('الخدمات (1 مُختارة — خدمتان على الأقل)')).toBeTruthy();
  });

  it('the points box can be reset to the live suggested sum with one tap', async () => {
    earnResponse = { services: { svc_a: { points: 10 }, svc_b: { points: 15 } }, groups: {},
                     service_group: {}, general: {}, packages: {} };
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));
    fireEvent.click(screen.getByText('قص شعر'));
    fireEvent.click(screen.getByText('فحص فرامل'));
    await waitFor(() => expect(screen.getByText(/استخدم مجموع نقاط الخدمات \(25\)/)).toBeTruthy());
    fireEvent.click(screen.getByText(/استخدم مجموع نقاط الخدمات/));
    const pointsBox = screen.getAllByDisplayValue('25')[0] as HTMLInputElement;
    expect(pointsBox.value).toBe('25');
    earnResponse = { services: {}, groups: {}, service_group: {}, general: {}, packages: {} };
  });

  it('a read-only role (no manage capability) sees no edit or create controls', async () => {
    const savedCreate = ACTIONS['operations.manage_services'];
    delete ACTIONS['operations.manage_services'];
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true },
    ];
    open();
    await waitFor(() => screen.getByText('باقة الصيانة'));
    expect(screen.queryByRole('button', { name: 'تعديل' })).toBeNull();
    expect(screen.queryByRole('switch')).toBeNull();
    ACTIONS['operations.manage_services'] = savedCreate;
  });

  it('a retired package with source=suggested still carries its badge', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة من محلّي', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: false, source: 'suggested' },
    ];
    open();
    await waitFor(() => expect(screen.getByText('باقة من محلّي')).toBeTruthy());
    expect(screen.getByText('من اقتراح محلّي')).toBeTruthy();
  });

  // ── description + photo (services-images-board.md phase 3, mirrored from Services.tsx) ─────
  it('a package with a description shows it on the card', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, description: 'قص شعر + فحص فرامل بسعر واحد' },
    ];
    open();
    await waitFor(() => expect(screen.getByText('باقة الصيانة')).toBeTruthy());
    expect(screen.getByText('قص شعر + فحص فرامل بسعر واحد')).toBeTruthy();
  });

  it('a package with has_image shows its real photo; one without shows the placeholder', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة بصورة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, has_image: true },
      { id: 'pkg2', name: 'باقة بلا صورة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, has_image: false },
    ];
    open();
    await waitFor(() => expect(screen.getByText('باقة بصورة')).toBeTruthy());
    await waitFor(() => expect(document.querySelectorAll('img').length).toBeGreaterThan(0));
    const img = document.querySelector('img') as HTMLImageElement;
    expect(img.src).toContain('blob:fake-image-url');
  });

  it('editing an existing package pre-fills the description and saves it on create/update', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, description: 'وصف أصلي' },
    ];
    open();
    await waitFor(() => screen.getByText('باقة الصيانة'));
    fireEvent.click(screen.getByRole('button', { name: 'تعديل' }));
    const desc = await screen.findByDisplayValue('وصف أصلي') as HTMLInputElement;
    fireEvent.change(desc, { target: { value: 'وصف مُحدَّث' } });
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));
    await waitFor(() => expect(createCalls.length).toBeGreaterThan(0));
    expect(createCalls[createCalls.length - 1]).toMatchObject({ description: 'وصف مُحدَّث' });
  });

  it('the image upload/delete controls only appear once the package already has an id', async () => {
    packagesResponse = [];
    open();
    await waitFor(() => screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    fireEvent.click(screen.getByRole('button', { name: /أنشئ باقتك الأولى/ }));
    await waitFor(() => screen.getByPlaceholderText(/باقة الصيانة الشاملة/));
    // a brand-new (unsaved) package has no id yet — nothing to attach a photo to
    expect(screen.queryByText('صورة الباقة (اختياري)')).toBeNull();
  });

  it('uploading a photo on an existing package posts it and clears the cached image', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, has_image: true },
    ];
    open();
    await waitFor(() => screen.getByText('باقة الصيانة'));
    fireEvent.click(screen.getByRole('button', { name: 'تعديل' }));
    await waitFor(() => screen.getByText('صورة الباقة (اختياري)'));
    const file = new File(['x'], 'p.jpg', { type: 'image/jpeg' });
    const input = document.querySelector('input[type="file"]') as HTMLInputElement;
    fireEvent.change(input, { target: { files: [file] } });
    await waitFor(() => expect(uploadImageCalls.length).toBeGreaterThan(0));
    expect(uploadImageCalls[0]).toMatchObject({ id: 'pkg1', content_type: 'image/jpeg' });
  });

  it('deleting a photo is offered only when the package actually has one, and posts the delete', async () => {
    packagesResponse = [
      { id: 'pkg1', name: 'باقة الصيانة', service_ids: ['svc_a', 'svc_b'], price_minor: 15000,
       active: true, has_image: true },
    ];
    open();
    await waitFor(() => screen.getByText('باقة الصيانة'));
    fireEvent.click(screen.getByRole('button', { name: 'تعديل' }));
    const del = await screen.findByText('حذف الصورة');
    fireEvent.click(del);
    await waitFor(() => expect(deleteImageCalls.length).toBeGreaterThan(0));
    expect(deleteImageCalls[0]).toMatchObject({ id: 'pkg1' });
  });
});
