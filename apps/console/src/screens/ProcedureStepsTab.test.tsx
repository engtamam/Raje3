/**
 * «الإجراءات» — the service list, per-service drawer (view/remove/save), the picker (search/
 * create), and the library drawer (create/edit/retire). Server calls mocked; the real request
 * shapes are covered on the backend side (services/operations/tests/integration/
 * test_procedure_steps_api.py).
 */
import { beforeEach, describe, expect, it } from 'vitest';
import { fireEvent, render as rtlRender, screen, waitFor } from '@testing-library/react';
import type { ReactElement } from 'react';
import { vi } from 'vitest';
import { OperatorI18nProvider } from '../operator-i18n';

const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const ACTIONS: Record<string, { id: string; label: string; method: string; path: string }> = {
  'operations.list_procedure_steps': { id: 'operations.list_procedure_steps', label: 'x', method: 'GET', path: '/procedure-steps' },
  'operations.manage_services': { id: 'operations.manage_services', label: 'x', method: 'GET', path: '/services' },
  'operations.create_procedure_step': { id: 'operations.create_procedure_step', label: 'x', method: 'POST', path: '/procedure-steps' },
  'operations.update_procedure_step': { id: 'operations.update_procedure_step', label: 'x', method: 'PATCH', path: '/procedure-steps/{id}' },
  'operations.update_service': { id: 'operations.update_service', label: 'x', method: 'PATCH', path: '/services/{id}' },
  'operations.export_procedure_checklist': { id: 'operations.export_procedure_checklist', label: 'x', method: 'POST', path: '/procedure-checklist/export' },
};

let stepsResponse: unknown[] = [
  { id: 'step_a', text: 'اغسل بالماء', severity: 'normal', active: true },
  { id: 'step_b', text: 'اربط الصمولة بعزم صحيح', severity: 'critical', active: true },
];
let servicesResponse: unknown[] = [
  { id: 'svc_1', name: 'غسيل خارجي', active: true, procedure_step_ids: ['step_a'] },
  { id: 'svc_2', name: 'غسيل شامل', active: true, procedure_step_ids: ['step_a', 'step_b'] },
];
const updateServiceCalls: unknown[] = [];
const createStepCalls: unknown[] = [];
const updateStepCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ACTIONS[id] ?? null,
    call: async (_session: unknown, a: { id: string }, body: unknown) => {
      if (a.id === 'operations.list_procedure_steps') return { procedure_steps: stepsResponse };
      if (a.id === 'operations.manage_services') return { services: servicesResponse };
      if (a.id === 'operations.update_service') { updateServiceCalls.push(body); return {}; }
      if (a.id === 'operations.create_procedure_step') {
        createStepCalls.push(body);
        const b = body as { text: string; severity: string };
        return { id: 'step_new', text: b.text, severity: b.severity, active: true };
      }
      if (a.id === 'operations.update_procedure_step') { updateStepCalls.push(body); return {}; }
      return {};
    },
  };
});

const { ProcedureStepsTab } = await import('./ProcedureStepsTab');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

function open() {
  return render(<ProcedureStepsTab session={session} catalog={catalog} />);
}

describe('الإجراءات', () => {
  // FRESH ARRAYS EVERY TEST — `ServiceDrawer`'s `onCreated` pushes straight onto the `steps`
  // array it was handed (the same object identity as this file's own `stepsResponse`), so a
  // previous test's "create a new step" leaks into the next one without this reset.
  beforeEach(() => {
    stepsResponse = [
      { id: 'step_a', text: 'اغسل بالماء', severity: 'normal', active: true },
      { id: 'step_b', text: 'اربط الصمولة بعزم صحيح', severity: 'critical', active: true },
    ];
    servicesResponse = [
      { id: 'svc_1', name: 'غسيل خارجي', active: true, procedure_step_ids: ['step_a'] },
      { id: 'svc_2', name: 'غسيل شامل', active: true, procedure_step_ids: ['step_a', 'step_b'] },
    ];
    updateServiceCalls.length = 0;
    createStepCalls.length = 0;
    updateStepCalls.length = 0;
  });

  it('lists services with their own step count', async () => {
    open();
    await waitFor(() => expect(screen.getByText('غسيل خارجي')).toBeTruthy());
    expect(screen.getByText('غسيل شامل')).toBeTruthy();
  });

  it('opens a services own drawer with its ordered steps, showing the shared-usage badge', async () => {
    open();
    await waitFor(() => screen.getByText('غسيل شامل'));
    fireEvent.click(screen.getByText('غسيل شامل'));
    await waitFor(() => expect(screen.getByText('اغسل بالماء')).toBeTruthy());
    expect(screen.getByText('اربط الصمولة بعزم صحيح')).toBeTruthy();
    // step_a is used by BOTH svc_1 and svc_2 — the shared-usage cue must show inside svc_2's own
    // drawer (the whole point of [[task-service-procedure-checklists]]'s own design).
    expect(screen.getByText('مستخدمة بـ2 خدمات')).toBeTruthy();
  });

  it('printing a services checklist downloads the branded PDF', async () => {
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob });
    vi.stubGlobal('fetch', fetchMock);
    const createObjectURL = vi.fn().mockReturnValue('blob:fake');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', { ...URL, createObjectURL, revokeObjectURL });

    open();
    await waitFor(() => screen.getByText('غسيل شامل'));
    fireEvent.click(screen.getByText('غسيل شامل'));
    await waitFor(() => expect(screen.getByText('اغسل بالماء')).toBeTruthy());

    fireEvent.click(screen.getByText('طباعة بطاقة الإجراءات'));
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/procedure-checklist/export'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ service_ids: ['svc_2'], file_format: 'pdf' }),
      }),
    ));
    await waitFor(() => expect(createObjectURL).toHaveBeenCalledWith(blob));

    vi.unstubAllGlobals();
  });

  it('selecting more than one service and printing sends one combined request', async () => {
    const blob = new Blob(['%PDF-1.4'], { type: 'application/pdf' });
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, blob: async () => blob });
    vi.stubGlobal('fetch', fetchMock);
    vi.stubGlobal('URL', { ...URL, createObjectURL: vi.fn().mockReturnValue('blob:fake'), revokeObjectURL: vi.fn() });

    open();
    await waitFor(() => screen.getByText('غسيل خارجي'));
    fireEvent.click(screen.getByLabelText('تحديد غسيل خارجي'));
    fireEvent.click(screen.getByLabelText('تحديد غسيل شامل'));

    await waitFor(() => expect(screen.getByText('2 خدمات محدَّدة')).toBeTruthy());
    fireEvent.click(screen.getByText('طباعة قائمة موحّدة'));

    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/procedure-checklist/export'),
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ service_ids: ['svc_1', 'svc_2'], file_format: 'pdf' }),
      }),
    ));

    vi.unstubAllGlobals();
  });

  it('removing a step and saving writes the new ordered list back to the service', async () => {
    open();
    await waitFor(() => screen.getByText('غسيل شامل'));
    fireEvent.click(screen.getByText('غسيل شامل'));
    await waitFor(() => screen.getByText('اربط الصمولة بعزم صحيح'));

    fireEvent.click(screen.getAllByLabelText('إزالة')[1]); // remove step_b
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));

    await waitFor(() => expect(updateServiceCalls.length).toBe(1));
    expect(updateServiceCalls[0]).toMatchObject({ id: 'svc_2', procedure_step_ids: ['step_a'] });
  });

  it('the picker excludes steps already on the service and lets you add one from the library', async () => {
    open();
    await waitFor(() => screen.getByText('غسيل خارجي'));
    fireEvent.click(screen.getByText('غسيل خارجي')); // svc_1 already has step_a only
    await waitFor(() => screen.getByText('اغسل بالماء'));

    fireEvent.click(screen.getByText('+ إضافة خطوة'));
    await waitFor(() => expect(screen.getByText('اربط الصمولة بعزم صحيح')).toBeTruthy());
    // step_a must not appear twice in the picker (already on this service).
    expect(screen.getAllByText('اغسل بالماء')).toHaveLength(1);

    fireEvent.click(screen.getByText('اربط الصمولة بعزم صحيح'));
    fireEvent.click(screen.getByRole('button', { name: /إضافة \(1\)/ }));
    fireEvent.click(screen.getByRole('button', { name: 'حفظ' }));

    await waitFor(() => expect(updateServiceCalls.length).toBe(1));
    expect(updateServiceCalls[0]).toMatchObject({ id: 'svc_1', procedure_step_ids: ['step_a', 'step_b'] });
  });

  it('creating a brand-new step from the picker adds it to the library and selects it', async () => {
    open();
    await waitFor(() => screen.getByText('غسيل خارجي'));
    fireEvent.click(screen.getByText('غسيل خارجي'));
    await waitFor(() => screen.getByText('اغسل بالماء'));
    fireEvent.click(screen.getByText('+ إضافة خطوة'));

    fireEvent.change(screen.getByPlaceholderText('أو اكتب خطوة جديدة كليًا…'), {
      target: { value: 'خطوة جديدة كليًا' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'إنشاء' }));

    await waitFor(() => expect(createStepCalls.length).toBe(1));
    expect(createStepCalls[0]).toMatchObject({ text: 'خطوة جديدة كليًا', severity: 'normal' });
    expect(screen.getByRole('button', { name: /إضافة \(1\)/ })).toBeTruthy();
  });

  it('the library drawer edits a steps severity directly', async () => {
    open();
    await waitFor(() => expect(screen.getByText(/مكتبة الإجراءات الكاملة/)).toBeTruthy());
    fireEvent.click(screen.getByText(/مكتبة الإجراءات الكاملة/));
    await waitFor(() => expect(screen.getAllByDisplayValue('اغسل بالماء').length).toBeGreaterThan(0));

    // SCOPED TO STEP_A'S OWN ROW — the library drawer's "add new step" form also defaults its own
    // severity select to "عادية", so a bare `getAllByDisplayValue('عادية')` matches both.
    const row = screen.getByDisplayValue('اغسل بالماء').closest('div') as HTMLElement;
    const select = row.querySelector('select') as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'critical' } });

    await waitFor(() => expect(updateStepCalls.length).toBe(1));
    expect(updateStepCalls[0]).toMatchObject({ id: 'step_a', severity: 'critical' });
  });

  it('the library drawer retires a step rather than deleting it', async () => {
    open();
    await waitFor(() => screen.getByText(/مكتبة الإجراءات الكاملة/));
    fireEvent.click(screen.getByText(/مكتبة الإجراءات الكاملة/));
    await waitFor(() => expect(screen.getAllByText('تعطيل').length).toBeGreaterThan(0));

    fireEvent.click(screen.getAllByText('تعطيل')[0]);

    await waitFor(() => expect(updateStepCalls.length).toBe(1));
    expect(updateStepCalls[0]).toMatchObject({ id: 'step_a', active: false });
  });
});
