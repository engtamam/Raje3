/**
 * مفاتيح المزوّدين الخارجيين — الاختبارات تتأكد أن الشاشة لا تعرض قيمة أبداً (آخر أربعة أحرف
 * فقط)، وأن التحديث يمرّ عبر تأكيد قبل استدعاء secrets.update، وأن غياب الصلاحية يُقال صراحة.
 *
 * بطاقة "الأسرار" واحدة لكل فئة (2026-09-07): كل مفاتيح الفئة (Meta، الذكاء الاصطناعي، بوابة
 * الدفع...) معاً بنافذة واحدة تُفتح بالنقر على بطاقة "الأسرار" — لا بطاقة منفصلة لكل مفتاح، ولا
 * تمرير طويل. `openSecrets` أدناه تفتح هذه البطاقة قبل أي تفاعل مع حقولها.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { AdminProviderSecrets } from './AdminProviderSecrets';
import type { AdminSession } from './api';

const SESSION: AdminSession = { access_token: 'tok-1' };

const CATALOG = {
  services: [
    { service: 'secrets-admin', actions: [
      { id: 'secrets.list', label: 'x', method: 'GET' as const,
       path: '/api/v1/secrets', capability: 'platform.secrets_manage' },
      { id: 'secrets.update', label: 'x', method: 'POST' as const,
       path: '/api/v1/secrets/{key}', capability: 'platform.secrets_manage', confirm: true,
       params: [{ name: 'key', in: 'path' as const, type: 'string', required: true }] },
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

// شاشة التبويبات: كل مزوّد فئته الخاصة، والتسمية تحمل عدّاده كذلك ("Meta (1/2)") — لذا مطابقة
// جزئية (RegExp) لا نص حرفي كامل. الاختبارات تفتح فئة المزوّد أول شي.
async function openProvider(label: string | RegExp) {
  await waitFor(() => expect(screen.getByText(label)).toBeTruthy());
  fireEvent.click(screen.getByText(label));
}

/** تفتح بطاقة "الأسرار" المجمَّعة لكل مفاتيح الفئة الحالية معاً. */
async function openSecrets() {
  await waitFor(() => expect(screen.getByText('الأسرار')).toBeTruthy());
  fireEvent.click(screen.getByText('الأسرار'));
  await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
}

/** تفتح بطاقة مصغّرة ثانية (إعداد تشغيل، معاينة) باسمها — بنفس نمط `openSecrets`. */
async function openCard(label: string | RegExp) {
  await waitFor(() => expect(screen.getByText(label)).toBeTruthy());
  fireEvent.click(screen.getByText(label));
  await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
}

describe('AdminProviderSecrets', () => {
  it('shows only the last four characters, never a value, right on the "الأسرار" card before it is even opened', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                 last4: 'ab12', updated_at: '2026-08-01T00:00:00Z', updated_by: 'op-1' }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^Meta\b/);
    // الحالة الإجمالية على البطاقة نفسها، بلا فتح — لا يوجد اسم المفتاح ولا آخر أربعة أحرف هنا
    // بعد (تلك داخل النافذة)، لكن العدّاد (1/1 مُعدّ) كافٍ للمحة سريعة.
    await waitFor(() => expect(screen.getByText('1/1 مُعدّ')).toBeTruthy());
    expect(screen.queryByRole('dialog')).toBeNull();

    await openSecrets();
    expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy();
    expect(screen.getByText('····ab12')).toBeTruthy();
    // NEVER THE RAW VALUE, NOT EVEN AS A KEY NAME IN A DATA ATTRIBUTE THE DOM WOULD EXPOSE.
    expect(screen.queryByText(/value/i)).toBeNull();

    // آخر تحديث يُعرض مُنسَّقاً (لا ISO خام كـ"2026-08-01T00:00:00Z")، وبلا معرّف المشغّل
    // التقني الخام ("op-1") — لا مكان بالمنصة كلها يحوّله لاسم حقيقي حالياً.
    await waitFor(() => expect(screen.getByText(/آخر تحديث:/)).toBeTruthy());
    expect(screen.queryByText(/2026-08-01T00:00:00Z/)).toBeNull();
    expect(screen.queryByText(/op-1/)).toBeNull();
    expect(screen.getByText(/آخر تحديث:/).textContent).toMatch(/أغسطس/);
  });

  it('an unreadable row says so inside the "الأسرار" dialog, never a false "غير مُعدّ"', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: null,
                 last4: null, updated_at: null, updated_by: null, unreadable: true }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^Meta\b/);
    await openSecrets();
    await waitFor(() => expect(screen.getByText(/تعذّر الاتصال بالعنقود/)).toBeTruthy());
  });

  it('opening "الأسرار" shows every key\'s form in one dialog; updating one arms an inline confirm step before calling secrets.update, and clears the field', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn()
      .mockResolvedValueOnce({
        secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي', configured: false,
                   last4: null, updated_at: null, updated_by: null }],
      })
      .mockResolvedValueOnce({ key: 'ASSISTANT_MODEL_CREDENTIAL', last4: 'zz99', updated_at: 'x' })
      .mockResolvedValueOnce({
        secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي', configured: true,
                   last4: 'zz99', updated_at: 'x', updated_by: 'op-1' }],
      });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^الذكاء الاصطناعي/);
    await waitFor(() => expect(screen.getByText('0/1 مُعدّ')).toBeTruthy());
    // NO DIALOG UNTIL "الأسرار" IS CLICKED — the long inline form is gone from the page itself.
    expect(screen.queryByRole('dialog')).toBeNull();
    await openSecrets();
    await waitFor(() => expect(screen.getByText('مفتاح الذكاء الاصطناعي')).toBeTruthy());

    const input = screen.getByLabelText('القيمة الجديدة') as HTMLInputElement;
    expect(input.type).toBe('password');
    fireEvent.change(input, { target: { value: 'AQ.new-real-key' } });
    fireEvent.click(screen.getByText('تحديث'));

    // NOT CALLED YET — the confirm step (inline, inside the same dialog) must gate the write.
    expect(reqMock).not.toHaveBeenCalledWith(
      '/api/v1/secrets/ASSISTANT_MODEL_CREDENTIAL', 'POST', expect.anything(), 'tok-1',
    );
    await waitFor(() => expect(screen.getByText(/تحديث "مفتاح الذكاء الاصطناعي"؟/)).toBeTruthy());
    // STILL ONE DIALOG, NOT TWO — the confirm step replaces the row's own content in place rather
    // than stacking a second Modal on top of it (this app's shared Modal does not support stacking).
    expect(screen.getAllByRole('dialog')).toHaveLength(1);

    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/secrets/ASSISTANT_MODEL_CREDENTIAL', 'POST', { value: 'AQ.new-real-key' }, 'tok-1',
    ));
    // THE FIELD IS EMPTY AGAIN — nothing typed here survives past the request.
    await waitFor(() => expect((screen.getByLabelText('القيمة الجديدة') as HTMLInputElement).value).toBe(''));
  });

  it('groups keys into one tab per provider, first tab shown by default, one shown at a time', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [
        { key: 'META_APP_ID', label: 'معرّف تطبيق ميتا', configured: true, last4: '1234', updated_at: null, updated_by: null },
        { key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: false, last4: null, updated_at: null, updated_by: null },
        { key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي', configured: false, last4: null, updated_at: null, updated_by: null },
      ],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    // Meta is first-to-appear in the response, so its tab is shown by default — its own tally
    // (1/2 configured) is now a colour-coded badge NEXT TO the tab's label (Segmented's own
    // `badge` prop), not baked into one text node, so the label and count are asserted separately.
    await waitFor(() => expect(screen.getByText('Meta')).toBeTruthy());
    expect(screen.getByText('1/2')).toBeTruthy();
    await openSecrets();
    expect(screen.getByText('معرّف تطبيق ميتا')).toBeTruthy();
    expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy();
    // the OTHER provider's keys are not in THIS dialog
    expect(screen.queryByText('مفتاح الذكاء الاصطناعي')).toBeNull();
    fireEvent.click(screen.getByLabelText('إغلاق'));

    // switching tabs shows the second provider's own "الأسرار" card, its own dialog
    fireEvent.click(screen.getByText(/^الذكاء الاصطناعي/));
    await openSecrets();
    await waitFor(() => expect(screen.getByText('مفتاح الذكاء الاصطناعي')).toBeTruthy());
    expect(screen.queryByText('معرّف تطبيق ميتا')).toBeNull();
  });

  it('no capability, no tab that quietly does nothing — the screen says so', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue({ services: [], unreachable: [] });
    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('هذه الشاشة ليست ضمن صلاحياتك')).toBeTruthy());
  });

  it('shows the env var name inside the dialog, and "؟" reveals where to get the value', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي', configured: false,
                 last4: null, updated_at: null, updated_by: null }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^الذكاء الاصطناعي/);
    await openSecrets();
    await waitFor(() => expect(screen.getByText('ASSISTANT_MODEL_CREDENTIAL')).toBeTruthy());

    expect(screen.queryByText(/Service Accounts/)).toBeNull();   // collapsed by default
    fireEvent.click(screen.getByLabelText(/ايش هذا؟/));
    expect(screen.getByText(/Service Accounts/)).toBeTruthy();
  });

  it('generating WHATSAPP_WEBHOOK_VERIFY_TOKEN fills a strong random value and reveals it to copy', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'WHATSAPP_WEBHOOK_VERIFY_TOKEN', label: 'توكن تحقق الـwebhook',
                 configured: false, last4: null, updated_at: null, updated_by: null }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^Meta\b/);
    await openSecrets();
    await waitFor(() => expect(screen.getByText('توليد')).toBeTruthy());

    const input = screen.getByLabelText('القيمة الجديدة') as HTMLInputElement;
    expect(input.type).toBe('password');
    fireEvent.click(screen.getByText('توليد'));

    // revealed as plain text so it can actually be read and pasted into Meta's own webhook config
    expect(input.type).toBe('text');
    expect(input.value.length).toBeGreaterThan(30);   // 32 random bytes, base64url — long, not a placeholder

    // typing over the generated value un-reveals it again — it is no longer the fresh value shown
    fireEvent.change(input, { target: { value: 'hand-typed' } });
    expect(input.type).toBe('password');
  });

  it('groups the payment-gateway credentials into their own provider\'s "الأسرار" card, with no gateway name hardcoded', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [
        { key: 'PAYMENT_API_KEY', label: 'اسم مستخدم بوابة الدفع', configured: false,
         last4: null, updated_at: null, updated_by: null },
        { key: 'PAYMENT_EXTRA_ID', label: 'معرّف إضافي لبوابة الدفع', configured: false,
         last4: null, updated_at: null, updated_by: null },
        { key: 'PAYMENT_EXTRA_SECRET', label: 'كلمة مرور بوابة الدفع', configured: false,
         last4: null, updated_at: null, updated_by: null },
      ],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^بوابة الدفع/);
    await openSecrets();
    await waitFor(() => expect(screen.getByText('اسم مستخدم بوابة الدفع')).toBeTruthy());
    expect(screen.getByText('معرّف إضافي لبوابة الدفع')).toBeTruthy();
    expect(screen.getByText('كلمة مرور بوابة الدفع')).toBeTruthy();
    // NO SPECIFIC GATEWAY NAME ANYWHERE ON SCREEN — the slot is generic because
    // PAYMENT_GATEWAY_DRIVER can change, and a label naming today's gateway would silently
    // describe the wrong one after a switch.
    expect(screen.queryByText(/تويق باي|tuwaiqpay|moyasar|stripe/i)).toBeNull();
  });

  it('the AI category shows a "المسار" selector (one path today) and splits into "الإدارة"/"المحاسبة", with a live model/behaviour panel and a read-only persona preview', async () => {
    const AI_CATALOG = {
      services: [
        { service: 'secrets-admin', actions: CATALOG.services[0].actions },
        { service: 'whatsapp-assistant', actions: [
          { id: 'whatsapp_assistant.operator_config', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/config', capability: 'platform.config' },
          { id: 'whatsapp_assistant.set_operator_config', label: 'x', method: 'PUT' as const,
           path: '/api/v1/assistant/operator/config', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.clear_operator_config', label: 'x', method: 'DELETE' as const,
           path: '/api/v1/assistant/operator/config/{key}', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.persona_preview', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/persona-preview', capability: 'platform.config' },
          { id: 'whatsapp_assistant.pricing_pending', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/pending', capability: 'platform.config' },
          { id: 'whatsapp_assistant.schedule_pricing', label: 'x', method: 'POST' as const,
           path: '/api/v1/assistant/operator/pricing/schedule', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.cancel_pending_pricing', label: 'x', method: 'DELETE' as const,
           path: '/api/v1/assistant/operator/pricing/pending/{key}', capability: 'platform.config', confirm: true },
        ] },
      ],
      unreachable: [],
    };
    fetchCatalogMock = vi.fn().mockResolvedValue(AI_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي',
                     configured: false, last4: null, updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/assistant/operator/config') {
        return Promise.resolve({ config: { ASSISTANT_MODEL_NAME: 'gemini-2.5-flash' } });
      }
      if (path.startsWith('/api/v1/assistant/operator/persona-preview')) {
        return Promise.resolve({ prompt: 'أنت المساعد الرقمي...' });
      }
      if (path === '/api/v1/assistant/operator/pricing/pending') {
        return Promise.resolve({ pending: [] });
      }
      throw new Error(`unexpected path ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    // فئة الذكاء الاصطناعي هي الوحيدة الموجودة بهذه الاستجابة، فهي المفتوحة افتراضياً.
    // مسار واحد اليوم — نص عادي، بلا عنصر تحكّم لخيار إجباري وحيد (2026-09-08).
    await waitFor(() => expect(screen.getByText('مساعد واتساب المحلات')).toBeTruthy());
    expect(screen.queryByRole('radio', { name: 'مساعد واتساب المحلات' })).toBeNull();

    // وتبويب "الإدارة" هو الافتراضي.
    expect(screen.getByText('الإدارة')).toBeTruthy();
    expect(screen.getByText('المحاسبة')).toBeTruthy();

    // الثلاث بطاقات (الأسرار، النموذج والسلوك، الشخصية والسلوك) — بلا أي نافذة مفتوحة بعد.
    await waitFor(() => expect(screen.getByText('الأسرار')).toBeTruthy());
    expect(screen.getByText('النموذج والسلوك')).toBeTruthy();
    expect(screen.getByText('الشخصية والسلوك')).toBeTruthy();
    expect(screen.queryByRole('dialog')).toBeNull();

    // الأسرار مجمَّعة بنافذة واحدة.
    await openSecrets();
    await waitFor(() => expect(screen.getByText('مفتاح الذكاء الاصطناعي')).toBeTruthy());
    fireEvent.click(screen.getByLabelText('إغلاق'));

    // تعديل قيمة نموذج يمر عبر تأكيد قبل PUT — نفس انضباط الأسرار، داخل نافذة البطاقة. الآن قائمة
    // منسدلة مبوّبة حسب المزوّد (2026-09-09)، لا خانة كتابة حرة — لا نموذج آخر غير Google مفعّل بعد.
    await openCard('النموذج والسلوك');
    await waitFor(() => expect((screen.getByLabelText('النموذج') as HTMLSelectElement).value)
      .toBe('gemini-2.5-flash'));
    const modelSelect = screen.getByLabelText('النموذج') as HTMLSelectElement;
    fireEvent.change(modelSelect, { target: { value: 'gemini-3.5-pro' } });
    fireEvent.click(screen.getByRole('button', { name: 'تحديث' }));
    await waitFor(() => expect(screen.getByText(/تعديل "النموذج"؟/)).toBeTruthy());
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/assistant/operator/config', 'PUT',
      { key: 'ASSISTANT_MODEL_NAME', value: 'gemini-3.5-pro' }, 'tok-1',
    ));
    fireEvent.click(screen.getByLabelText('إغلاق'));

    // معاينة الشخصية بنافذتها الخاصة.
    await openCard('الشخصية والسلوك');
    await waitFor(() => expect(screen.getByText(/أنت المساعد الرقمي/)).toBeTruthy());
    fireEvent.click(screen.getByLabelText('إغلاق'));

    // "المحاسبة" تفتح إعدادات وحدات الذكاء الحقيقية، لا نص "قريباً".
    fireEvent.click(screen.getByText('المحاسبة'));
    await waitFor(() => expect(screen.getByText('إعدادات وحدات الذكاء')).toBeTruthy());
    expect(screen.queryByText('الأسرار')).toBeNull();
  });

  it('a bounded numeric knob refuses a value outside its own range before the network call', async () => {
    const AI_CATALOG = {
      services: [
        { service: 'secrets-admin', actions: CATALOG.services[0].actions },
        { service: 'whatsapp-assistant', actions: [
          { id: 'whatsapp_assistant.operator_config', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/config', capability: 'platform.config' },
          { id: 'whatsapp_assistant.set_operator_config', label: 'x', method: 'PUT' as const,
           path: '/api/v1/assistant/operator/config', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.clear_operator_config', label: 'x', method: 'DELETE' as const,
           path: '/api/v1/assistant/operator/config/{key}', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.persona_preview', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/persona-preview', capability: 'platform.config' },
          { id: 'whatsapp_assistant.pricing_pending', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/pending', capability: 'platform.config' },
        ] },
      ],
      unreachable: [],
    };
    fetchCatalogMock = vi.fn().mockResolvedValue(AI_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي',
                     configured: false, last4: null, updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/assistant/operator/config') {
        // Meta's own carousel bounds are 2-10 — see app/config.py's own field_validator.
        return Promise.resolve({ config: { MAX_CAROUSEL_CARDS: 5 } });
      }
      if (path.startsWith('/api/v1/assistant/operator/persona-preview')) {
        return Promise.resolve({ prompt: 'أنت المساعد الرقمي...' });
      }
      if (path === '/api/v1/assistant/operator/pricing/pending') {
        return Promise.resolve({ pending: [] });
      }
      throw new Error(`unexpected path ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openCard('النموذج والسلوك');
    await waitFor(() => expect((screen.getByLabelText('أقصى بطاقات بالعرض') as HTMLInputElement).value)
      .toBe('5'));
    const cardsInput = screen.getByLabelText('أقصى بطاقات بالعرض') as HTMLInputElement;
    const updateButton = screen.getByRole('button', { name: 'تحديث' }) as HTMLButtonElement;

    // 11 is past Meta's own 10-card ceiling — refused before any PUT is even attempted.
    fireEvent.change(cardsInput, { target: { value: '11' } });
    expect(updateButton.disabled).toBe(true);
    expect(screen.getByText(/يجب أن تكون قيمة صحيحة بين 2 و10/)).toBeTruthy();

    // Back inside bounds re-enables it, and the PUT that follows carries the corrected value.
    fireEvent.change(cardsInput, { target: { value: '8' } });
    expect(updateButton.disabled).toBe(false);
    fireEvent.click(updateButton);
    await waitFor(() => expect(screen.getByText(/تعديل "أقصى بطاقات بالعرض"؟/)).toBeTruthy());
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/assistant/operator/config', 'PUT',
      { key: 'MAX_CAROUSEL_CARDS', value: '8' }, 'tok-1',
    ));
  });

  it('picking a model with no registered price warns before it ever reaches the network', async () => {
    const AI_CATALOG = {
      services: [
        { service: 'secrets-admin', actions: CATALOG.services[0].actions },
        { service: 'whatsapp-assistant', actions: [
          { id: 'whatsapp_assistant.operator_config', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/config', capability: 'platform.config' },
          { id: 'whatsapp_assistant.set_operator_config', label: 'x', method: 'PUT' as const,
           path: '/api/v1/assistant/operator/config', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.clear_operator_config', label: 'x', method: 'DELETE' as const,
           path: '/api/v1/assistant/operator/config/{key}', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.persona_preview', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/persona-preview', capability: 'platform.config' },
          { id: 'whatsapp_assistant.pricing_pending', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/pending', capability: 'platform.config' },
        ] },
      ],
      unreachable: [],
    };
    fetchCatalogMock = vi.fn().mockResolvedValue(AI_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي',
                     configured: false, last4: null, updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/assistant/operator/config') {
        // gemini-3.1-flash-lite is priced; gemini-2.5-flash (the CURRENT live model) is not.
        return Promise.resolve({
          config: {
            ASSISTANT_MODEL_NAME: 'gemini-2.5-flash',
            PRICING_AI_UNIT_MODEL_COSTS_JSON:
              '{"gemini-3.1-flash-lite": {"input_usd_per_million": 0.25, "output_usd_per_million": 1.5}}',
          },
        });
      }
      if (path.startsWith('/api/v1/assistant/operator/persona-preview')) {
        return Promise.resolve({ prompt: 'أنت المساعد الرقمي...' });
      }
      if (path === '/api/v1/assistant/operator/pricing/pending') {
        return Promise.resolve({ pending: [] });
      }
      throw new Error(`unexpected path ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openCard('النموذج والسلوك');
    const modelSelect = await waitFor(
      () => screen.getByLabelText('النموذج') as HTMLSelectElement);

    // The live model (gemini-2.5-flash) has no cost entry — warned immediately, no interaction needed.
    expect(screen.getByText(/هذا النموذج بلا سعر مسجَّل/)).toBeTruthy();

    // Switching to the priced model clears the warning.
    fireEvent.change(modelSelect, { target: { value: 'gemini-3.1-flash-lite' } });
    expect(screen.queryByText(/هذا النموذج بلا سعر مسجَّل/)).toBeNull();

    // Switching to an unpriced-but-wired model brings it back.
    fireEvent.change(modelSelect, { target: { value: 'gpt-oss-120b' } });
    expect(screen.getByText(/هذا النموذج بلا سعر مسجَّل/)).toBeTruthy();
  });

  it('المحاسبة schedules the five AI-unit pricing keys together on "جدولة إعدادات وحدات الذكاء"', async () => {
    const AI_CATALOG = {
      services: [
        { service: 'secrets-admin', actions: CATALOG.services[0].actions },
        { service: 'whatsapp-assistant', actions: [
          { id: 'whatsapp_assistant.pricing_pending', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/pending', capability: 'platform.config' },
          { id: 'whatsapp_assistant.schedule_pricing', label: 'x', method: 'POST' as const,
           path: '/api/v1/assistant/operator/pricing/schedule', capability: 'platform.config', confirm: true },
          { id: 'whatsapp_assistant.cancel_pending_pricing', label: 'x', method: 'DELETE' as const,
           path: '/api/v1/assistant/operator/pricing/pending/{key}', capability: 'platform.config', confirm: true },
        ] },
      ],
      unreachable: [],
    };
    fetchCatalogMock = vi.fn().mockResolvedValue(AI_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string, method?: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي',
                     configured: false, last4: null, updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/assistant/operator/pricing/pending') return Promise.resolve({ pending: [] });
      if (path === '/api/v1/assistant/operator/pricing/schedule' && method === 'POST') {
        return Promise.resolve({ key: 'x', value: 'x', effective_at: 0 });
      }
      throw new Error(`unexpected ${method} ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    // فئة الذكاء الاصطناعي هي الوحيدة، والحاسبة ليست التبويب الافتراضي — نفتحها.
    await waitFor(() => expect(screen.getByText('المحاسبة')).toBeTruthy());
    fireEvent.click(screen.getByText('المحاسبة'));
    await waitFor(() => expect(screen.getByText('إعدادات وحدات الذكاء')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'جدولة إعدادات وحدات الذكاء' }));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/assistant/operator/pricing/schedule', 'POST',
      { key: 'PRICING_AI_UNIT_UNITS_PER_HALALA', value: 1000, effective_in_days: 15 }, 'tok-1',
    ));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/assistant/operator/pricing/schedule', 'POST',
      { key: 'PRICING_AI_UNIT_USD_TO_SAR', value: 3.75, effective_in_days: 15 }, 'tok-1',
    ));
    await waitFor(() => expect(screen.getByText('تمّت الجدولة.')).toBeTruthy());
  });

  it('المحاسبة previews real consumption per message from actual usage, not a guess', async () => {
    const AI_CATALOG = {
      services: [
        { service: 'secrets-admin', actions: CATALOG.services[0].actions },
        { service: 'whatsapp-assistant', actions: [
          { id: 'whatsapp_assistant.pricing_report', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/report', capability: 'platform.config' },
          { id: 'whatsapp_assistant.pricing_pending', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/pending', capability: 'platform.config' },
        ] },
      ],
      unreachable: [],
    };
    fetchCatalogMock = vi.fn().mockResolvedValue(AI_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي',
                     configured: false, last4: null, updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/assistant/operator/pricing/pending') return Promise.resolve({ pending: [] });
      if (path.startsWith('/api/v1/assistant/operator/pricing/report')) {
        return Promise.resolve({
          days: 30, calls: 100, conversations: 40, input_tokens: 30_000, output_tokens: 15_000,
          avg_input_tokens_per_call: 300, avg_output_tokens_per_call: 150,
          avg_calls_per_conversation: 2.5, truncated: false,
        });
      }
      throw new Error(`unexpected ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('المحاسبة')).toBeTruthy());
    fireEvent.click(screen.getByText('المحاسبة'));
    await waitFor(() => expect(screen.getByText('إعدادات وحدات الذكاء')).toBeTruthy());

    // الأرقام الافتراضية (1000 وحدة/هللة، هامش 5/2، 3.75 صرف، gemini-3.1-flash-lite بسعره الحقيقي)
    // على متوسط فعلي 300 دخل + 150 خرج = ~309 وحدة، نفس المعادلة المُتحقَّق منها بـai_unit_pricing.py.
    const preview = await waitFor(() => screen.getByText(/300 دخل \+ 150 خرج/));
    expect(preview.textContent).toContain('309 وحدة');
  });

  it('المحاسبة lists a scheduled change with its real effective date, and "إلغاء" cancels the right key', async () => {
    const EFFECTIVE_AT = Math.floor(Date.now() / 1000) + 15 * 86_400;
    const AI_CATALOG = {
      services: [
        { service: 'secrets-admin', actions: CATALOG.services[0].actions },
        { service: 'whatsapp-assistant', actions: [
          { id: 'whatsapp_assistant.pricing_pending', label: 'x', method: 'GET' as const,
           path: '/api/v1/assistant/operator/pricing/pending', capability: 'platform.config' },
          { id: 'whatsapp_assistant.cancel_pending_pricing', label: 'x', method: 'DELETE' as const,
           path: '/api/v1/assistant/operator/pricing/pending/{key}', capability: 'platform.config', confirm: true },
        ] },
      ],
      unreachable: [],
    };
    fetchCatalogMock = vi.fn().mockResolvedValue(AI_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string, method?: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'ASSISTANT_MODEL_CREDENTIAL', label: 'مفتاح الذكاء الاصطناعي',
                     configured: false, last4: null, updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/assistant/operator/pricing/pending') {
        return Promise.resolve({
          pending: [{ key: 'PRICING_AI_UNIT_USD_TO_SAR', value: 4,
                     effective_at: EFFECTIVE_AT, scheduled_by: 'op1', scheduled_at: 0 }],
        });
      }
      if (method === 'DELETE') return Promise.resolve({ cancelled: true });
      throw new Error(`unexpected ${method} ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await waitFor(() => expect(screen.getByText('المحاسبة')).toBeTruthy());
    fireEvent.click(screen.getByText('المحاسبة'));

    await waitFor(() => expect(screen.getByText('سعر صرف الدولار')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'إلغاء' }));

    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/assistant/operator/pricing/pending/PRICING_AI_UNIT_USD_TO_SAR',
      'DELETE', undefined, 'tok-1',
    ));
  });

  // ── "الحالة" (Raje3 Meta-panel Phase 1) — رؤية تشغيلية فوق بطاقة "الأسرار"، مع لون حقيقي لكل
  // حالة اتصال ومعدّل إرسال حقيقي. ─────────────────────────────────────────────────────────────
  const STATUS_CATALOG = {
    services: [
      { service: 'secrets-admin', actions: CATALOG.services[0].actions },
      { service: 'operations', actions: [
        { id: 'operations.whatsapp_platform_status', label: 'x', method: 'GET' as const,
         path: '/api/v1/platform/whatsapp/platform-status', capability: 'platform.operations' },
      ] },
    ],
    unreachable: [],
  };

  it('renders "حالة واتساب المنصة" above "الأسرار" for Meta, with a connected number in success styling and a stopped one in danger styling', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(STATUS_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                     last4: 'ab12', updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/platform/whatsapp/platform-status') {
        return Promise.resolve({
          connections: {
            total: 2, by_state: { connected: 1, stopped: 1 },
            numbers: [
              { id: 'a', tenant: 'shop-a', state: 'connected', step: '', waba_id: '', phone_number_id: '',
               business_id: '', detail: '', at: 1_700_000_000, branch_id: '' },
              { id: 'b', tenant: 'shop-b', state: 'stopped', step: '', waba_id: '', phone_number_id: '',
               business_id: '', detail: '', at: 1_700_000_100, branch_id: '' },
            ],
          },
          peer_unavailable: false,
          deliveries: { sent: 40, failed: 10, queued: 0, delivered: 35, read: 20, total: 50, window_hours: 24 },
          numbers_bound: 2, marketing_opt_outs: 7,
        });
      }
      throw new Error(`unexpected path ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^Meta\b/);

    // الحالة تظهر — والأسرار كذلك، معاً بنفس الشاشة، "الحالة" فوقها.
    await waitFor(() => expect(screen.getByText('حالة واتساب المنصة')).toBeTruthy());
    expect(screen.getByText('الأسرار')).toBeTruthy();

    // أرقام حقيقية بالمؤشرات، لا نص "قريباً".
    await waitFor(() => expect(screen.getByTestId('kpi-sent').textContent).toContain('40'));
    expect(screen.getByTestId('kpi-failed').textContent).toContain('10');
    expect(screen.getByTestId('kpi-numbers-bound').textContent).toContain('2');
    expect(screen.getByTestId('kpi-opt-outs').textContent).toContain('7');

    // اللون الحقيقي: مربوط أخضر (success)، متوقف أحمر (danger) — لا نفس اللون للاثنين.
    const connectedBadge = screen.getByText('مربوط');
    const stoppedBadge = screen.getByText('متوقف');
    expect(connectedBadge.closest('span')?.className).toContain('success');
    expect(stoppedBadge.closest('span')?.className).toContain('danger');
    expect(connectedBadge.closest('span')?.className)
      .not.toBe(stoppedBadge.closest('span')?.className);
  });

  it('an unreachable notification-service still shows connection state, and says the rest is unavailable', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(STATUS_CATALOG);
    reqMock = vi.fn().mockImplementation((path: string) => {
      if (path === '/api/v1/secrets') {
        return Promise.resolve({
          secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                     last4: 'ab12', updated_at: null, updated_by: null }],
        });
      }
      if (path === '/api/v1/platform/whatsapp/platform-status') {
        return Promise.resolve({
          connections: {
            total: 1, by_state: { connected: 1 },
            numbers: [{ id: 'a', tenant: 'shop-a', state: 'connected', step: '', waba_id: '',
                       phone_number_id: '', business_id: '', detail: '', at: 1_700_000_000, branch_id: '' }],
          },
          peer_unavailable: true, deliveries: null, numbers_bound: null, marketing_opt_outs: null,
        });
      }
      throw new Error(`unexpected path ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^Meta\b/);
    await waitFor(() => expect(screen.getByText(/تعذّر الاتصال بخدمة الإشعارات/)).toBeTruthy());
    // الاتصال المحلي (operations) لا يزال يُعرض بلا مشكلة رغم انقطاع notification-service.
    expect(screen.getByText('مربوط')).toBeTruthy();
    expect(screen.getByTestId('kpi-sent').textContent).toContain('—');
  });

  it('never renders any "reveal" or "show" control', async () => {
    fetchCatalogMock = vi.fn().mockResolvedValue(CATALOG);
    reqMock = vi.fn().mockResolvedValue({
      secrets: [{ key: 'META_APP_SECRET', label: 'سر تطبيق ميتا', configured: true,
                 last4: 'ab12', updated_at: null, updated_by: null }],
    });

    render(<AdminProviderSecrets session={SESSION} />);
    await openProvider(/^Meta\b/);
    await openSecrets();
    await waitFor(() => expect(screen.getByText('سر تطبيق ميتا')).toBeTruthy());
    // «تُعرض» legitimately appears in this screen's own reassurance copy ("القيمة لا تُعرض هنا
    // أبداً") — the real assertion is that no CONTROL offers to reveal one.
    expect(screen.queryByRole('button', { name: /عرض|إظهار|show|reveal/i })).toBeNull();
  });
});
