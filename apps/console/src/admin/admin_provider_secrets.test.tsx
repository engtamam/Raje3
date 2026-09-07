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
    // (1/2 configured) rides inside the tab's own label AND inside the "الأسرار" card for it.
    await waitFor(() => expect(screen.getByText(/^Meta \(1\/2\)/)).toBeTruthy());
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
      throw new Error(`unexpected path ${path}`);
    });

    render(<AdminProviderSecrets session={SESSION} />);
    // فئة الذكاء الاصطناعي هي الوحيدة الموجودة بهذه الاستجابة، فهي المفتوحة افتراضياً.
    await waitFor(() => expect(screen.getByText('المسار')).toBeTruthy());
    // مسار واحد اليوم، لكنه ظاهر ومُختار (radio مفرد داخل مجموعة حقيقية).
    const pathRadio = screen.getByRole('radio', { name: 'مساعد واتساب المحلات' });
    expect(pathRadio.getAttribute('aria-checked')).toBe('true');

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

    // تعديل قيمة نموذج يمر عبر تأكيد قبل PUT — نفس انضباط الأسرار، داخل نافذة البطاقة.
    await openCard('النموذج والسلوك');
    await waitFor(() => expect(screen.getByDisplayValue('gemini-2.5-flash')).toBeTruthy());
    const modelInput = screen.getByDisplayValue('gemini-2.5-flash') as HTMLInputElement;
    fireEvent.change(modelInput, { target: { value: 'gemini-3.0-flash' } });
    fireEvent.click(screen.getByRole('button', { name: 'تحديث' }));
    await waitFor(() => expect(screen.getByText(/تعديل "اسم النموذج"؟/)).toBeTruthy());
    fireEvent.click(screen.getByText('تأكيد'));
    await waitFor(() => expect(reqMock).toHaveBeenCalledWith(
      '/api/v1/assistant/operator/config', 'PUT',
      { key: 'ASSISTANT_MODEL_NAME', value: 'gemini-3.0-flash' }, 'tok-1',
    ));
    fireEvent.click(screen.getByLabelText('إغلاق'));

    // معاينة الشخصية بنافذتها الخاصة.
    await openCard('الشخصية والسلوك');
    await waitFor(() => expect(screen.getByText(/أنت المساعد الرقمي/)).toBeTruthy());
    fireEvent.click(screen.getByLabelText('إغلاق'));

    // "المحاسبة" مكانها محجوز، ما فيه شي مبني بعد — نص واضح لا شاشة فارغة تبدو معطّلة.
    fireEvent.click(screen.getByText('المحاسبة'));
    expect(screen.getByText(/الحاسبة المالية للذكاء الاصطناعي — قريباً/)).toBeTruthy();
    expect(screen.queryByText('الأسرار')).toBeNull();
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
