/**
 * Launch.tsx — the `package_offer` goal's own picker (packages feature). The service_offer path
 * is pre-existing and unchanged; this covers only the new branch: the "catalogue" blank fills
 * with a PACKAGE instead of a service, and the request carries package_id/package_name instead
 * of service_id/service_name.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render as rtlRender, screen, waitFor, within } from '@testing-library/react';
import type { ReactElement } from 'react';
import { OperatorI18nProvider } from '../operator-i18n';

// Launch now reads `useOperatorI18n()` — wrap once here so every existing `render(<...>)`
// call site below stays unchanged.
const SESSION_FOR_I18N = { tenant: 't1', operator: '', operatorName: '', token: 'tok' } as never;
function render(ui: ReactElement) {
  return rtlRender(<OperatorI18nProvider session={SESSION_FOR_I18N}>{ui}</OperatorI18nProvider>);
}

const ACTIONS: Record<string, { id: string; label: string; method: string; path: string }> = {
  'campaigns.goals': { id: 'campaigns.goals', label: 'x', method: 'GET', path: '/goals' },
  'campaigns.preview': { id: 'campaigns.preview', label: 'x', method: 'POST', path: '/preview' },
  'campaigns.create': { id: 'campaigns.create', label: 'x', method: 'POST', path: '' },
  'operations.list_services': { id: 'operations.list_services', label: 'x', method: 'GET', path: '/services' },
  'operations.list_packages': { id: 'operations.list_packages', label: 'x', method: 'GET', path: '/packages' },
  'operations.list_branches': { id: 'operations.list_branches', label: 'x', method: 'GET', path: '/branches' },
  'reminders.reasons': { id: 'reminders.reasons', label: 'x', method: 'GET', path: '/reasons' },
  'insights.dashboard': { id: 'insights.dashboard', label: 'x', method: 'GET', path: '/dashboard' },
};

const previewCalls: unknown[] = [];
const createCalls: unknown[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ACTIONS[id] ?? null,
    call: async (_session: unknown, a: { id: string }, body?: unknown) => {
      if (a.id === 'campaigns.goals') {
        return {
          goals: [
            { goal: 'package_offer', title: 'عرض على باقة', line: 'روّج لباقة',
             icon: 'tag', available: true, offers: true,
             blanks: ['amount', 'catalogue', 'date'], template_status: 'approved' },
            // A GOAL WITH A MATCHING «متى نرسل» REASON (win_back ↔ gone_missing) — the one
            // shape that earns the cross-link button.
            { goal: 'win_back', title: 'رجّع اللي غابوا', line: 'من تأخّر عن موعده',
             icon: 'return', available: true, offers: true, blanks: [] },
            { goal: 'service_offer', title: 'عرض على خدمة', line: 'يوصل فقط لمن قارب موعد',
             icon: 'tag', available: true, offers: true,
             blanks: ['amount', 'catalogue', 'date'] },
            // ITS OWN "catalogue" BLANK (2026-09-13's own multi-select expansion) — reward_loyal now
            // gets the SAME multi-select service/package picker `hasBlank(picked, 'catalogue')`
            // already draws for the other two, purely because its real template declares one.
            { goal: 'reward_loyal', title: 'كافئ المخلصين', line: 'الأكثر زيارة عندك',
             icon: 'gift', available: true, offers: true, blanks: ['catalogue'] },
          ],
        };
      }
      if (a.id === 'operations.list_services') {
        return {
          services: [
            { id: 'svc_popular', name: 'غسلة سريعة' },
            { id: 'svc_rare', name: 'تلميع كامل' },
            { id: 'svc_unseen', name: 'خدمة جديدة' },
          ],
        };
      }
      if (a.id === 'insights.dashboard') {
        return {
          values: {
            // svc_unseen carries NO row at all — the honest reading of "never promoted" (?? 0),
            // so it must still sort to the very front, ahead of svc_rare's real (low) count.
            service_popularity: [
              { service_id: 'svc_popular', count: 40 },
              { service_id: 'svc_rare', count: 2 },
            ],
          },
        };
      }
      if (a.id === 'operations.list_packages') {
        return { packages: [{ id: 'pkg1', name: 'باقة الصيانة', active: true }] };
      }
      if (a.id === 'operations.list_branches') return { branches: [] };
      if (a.id === 'reminders.reasons') {
        return {
          reasons: [{ id: 'gone_missing', label: 'تجاوز دورته ولم يعد',
                     when: 'حين يمضي على زيارته مرّة ونصف دورته المعتادة', can_retext: true }],
        };
      }
      if (a.id === 'campaigns.preview') { previewCalls.push(body); return { message: 'معاينة', reaches: 10 }; }
      if (a.id === 'campaigns.create') { createCalls.push(body); return { campaign: { id: 'cmp1' } }; }
      return {};
    },
  };
});

const { Launch } = await import('./Launch');

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

describe('package_offer', () => {
  it('shows a package select, not a service select, for the package_offer goal', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="package_offer" />);
    await waitFor(() => expect(screen.getByText('على أي باقة؟')).toBeTruthy());
    expect(screen.queryByText('على أي خدمة؟')).toBeNull();
    expect(screen.getByText('باقة الصيانة')).toBeTruthy();
  });

  it('preview sends package_ids, never service_ids', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="package_offer" />);
    await waitFor(() => screen.getByText('على أي باقة؟'));

    // THE PACKAGE PICKER IS A CHIP GROUP NOW (multi-select, 2026-09-13), not a <select> — press
    // the one chip this mock's catalogue offers.
    fireEvent.click(screen.getByRole('button', { name: 'باقة الصيانة' }));

    const amountBox = document.querySelector('input[type="number"]') as HTMLInputElement;
    fireEvent.change(amountBox, { target: { value: '20' } });
    const dateBox = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateBox, { target: { value: '2030-01-01' } });

    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));
    const body = previewCalls[0] as { package_ids: string[]; service_ids: string[] };
    expect(body.package_ids).toEqual(['pkg1']);
    expect(body.service_ids).toEqual([]);
  });
});

describe('the template-status badge on the goal picker', () => {
  it('shows the badge when the goal carries a known status', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} />);
    await waitFor(() => expect(screen.getByText('عرض على باقة')).toBeTruthy());
    expect(screen.getByText('معتمدة')).toBeTruthy();
  });
});

describe('the cross-link to «متى نرسل»', () => {
  it('offers to view/retext the message when the picked goal shares a reason', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="win_back" />);
    // THE TITLE NOW APPEARS TWICE (the always-visible rail's own row, AND the builder's header) —
    // the rail no longer disappears once a goal is picked (approved mockup's persistent 3-lane
    // layout, 2026-09-13), so this only asserts it rendered at all rather than exactly once.
    await waitFor(() => expect(screen.getAllByText('رجّع اللي غابوا').length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.getByText('عرض نص هذه الرسالة أو تعديله')).toBeTruthy());
  });

  it('offers nothing for a goal with no automatic counterpart', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="package_offer" />);
    await waitFor(() => expect(screen.getByText('على أي باقة؟')).toBeTruthy());
    expect(screen.queryByText('عرض نص هذه الرسالة أو تعديله')).toBeNull();
  });
});

describe('the service picker on «عرض على خدمة»', () => {
  it('orders services least-taken first, chain-wide — never taken sorts ahead of a low real count', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="service_offer" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    // THE SERVICE PICKER IS A CHIP GROUP NOW (multi-select, 2026-09-13) — its own `role="group"`
    // holds one button per service, in the same least-taken-first order the old <select> did.
    const group = screen.getByRole('group', { name: 'على أي خدمة؟' });
    const names = Array.from(group.querySelectorAll('button')).map((b) => b.textContent);
    expect(names).toEqual(['خدمة جديدة', 'تلميع كامل', 'غسلة سريعة']);
  });

  it('lets him pick more than one service, and sends all of them together', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="service_offer" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'تلميع كامل' }));

    const amountBox = document.querySelector('input[type="number"]') as HTMLInputElement;
    fireEvent.change(amountBox, { target: { value: '20' } });
    const dateBox = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateBox, { target: { value: '2030-01-01' } });

    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));
    const body = previewCalls[0] as { service_ids: string[]; service_names: string[] };
    expect(body.service_ids).toEqual(['svc_popular', 'svc_rare']);
    expect(body.service_names).toEqual(['غسلة سريعة', 'تلميع كامل']);

    // PRESSING AN ALREADY-CHOSEN CHIP AGAIN REMOVES IT — a real toggle, not a one-way add.
    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(2));
    expect((previewCalls[1] as { service_ids: string[] }).service_ids).toEqual(['svc_rare']);
  });
});

describe('the redeemable-item picker on «كافئ المخلصين»', () => {
  it('offers the same multi-select service picker — its own template also has a catalogue blank', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'تلميع كامل' }));

    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));
    const body = previewCalls[0] as { service_ids: string[]; goal: string };
    expect(body.goal).toBe('reward_loyal');
    expect(body.service_ids).toEqual(['svc_popular', 'svc_rare']);
  });
});

describe('the live audience-size sliders on «كافئ المخلصين»', () => {
  it('sends today\'s defaults (90 days / 3 visits) when the owner never touches either slider', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal" />);
    await waitFor(() => expect(screen.getByText('من هم عملاؤك المخلصون؟')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));
    const body = previewCalls[0] as { loyalty_window_days: number; loyalty_min_visits: number };
    expect(body.loyalty_window_days).toBe(90);
    expect(body.loyalty_min_visits).toBe(3);
  });

  it('dragging a slider after a preview exists re-asks with the new value, debounced', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal" />);
    await waitFor(() => expect(screen.getByText('من هم عملاؤك المخلصون؟')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));

    const slider = screen.getByTestId('loyalty-window-days') as HTMLInputElement;
    fireEvent.change(slider, { target: { value: '30' } });
    // NOT YET — the 300ms debounce has not elapsed.
    expect(previewCalls.length).toBe(1);

    await waitFor(() => expect(previewCalls.length).toBe(2), { timeout: 1000 });
    expect((previewCalls[1] as { loyalty_window_days: number }).loyalty_window_days).toBe(30);
  });

  it('never asks for a preview before the owner has pressed «عرض ما سيصل» once', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal" />);
    await waitFor(() => expect(screen.getByText('من هم عملاؤك المخلصون؟')).toBeTruthy());

    const slider = screen.getByTestId('loyalty-min-visits') as HTMLInputElement;
    fireEvent.change(slider, { target: { value: '10' } });
    await new Promise((r) => setTimeout(r, 350));
    expect(previewCalls.length).toBe(0);
  });
});

// ── the %/ريال toggle stuck on % until a number existed (2026-09-14 fix) ────────────────────────
describe('the discount-kind toggle switches even with an empty amount box', () => {
  it('switching to «ريال» with nothing typed yet is reflected immediately, not stuck on «%»', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="service_offer" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());

    const group = screen.getByRole('radiogroup', { name: 'نوع الخصم' });
    fireEvent.click(within(group).getByRole('radio', { name: 'ريال' }));
    expect(within(group).getByRole('radio', { name: 'ريال' }).getAttribute('aria-checked')).toBe('true');
    expect(within(group).getByRole('radio', { name: '%' }).getAttribute('aria-checked')).toBe('false');
  });

  it('a number typed after switching to «ريال» composes with ريال, not %', async () => {
    previewCalls.length = 0;
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="service_offer" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());

    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    const group = screen.getByRole('radiogroup', { name: 'نوع الخصم' });
    fireEvent.click(within(group).getByRole('radio', { name: 'ريال' }));
    const amountBox = document.querySelector('input[type="number"]') as HTMLInputElement;
    fireEvent.change(amountBox, { target: { value: '50' } });
    const dateBox = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateBox, { target: { value: '2030-01-01' } });

    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(previewCalls.length).toBe(1));
    expect((previewCalls[0] as { offer_value: string }).offer_value).toBe('50 ريال');
  });
});

// ── REWARD_ENABLED_GOALS gone stale (2026-09-13 fix) ────────────────────────────────────────────
// The client's own copy of the backend's REWARD_ENABLED_GOALS had frozen at the
// occasion/win_back pilot stage — service_offer and package_offer never saw the reward-type
// picker at all, silently defaulting to a plain discount.
describe('the reward-type picker now reaches service_offer and package_offer too', () => {
  it('shows the reward-type picker for service_offer', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="service_offer" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    expect(screen.getByText('ماذا تقدّم؟')).toBeTruthy();
  });

  it('shows the reward-type picker for package_offer', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="package_offer" />);
    await waitFor(() => expect(screen.getByText('على أي باقة؟')).toBeTruthy());
    expect(screen.getByText('ماذا تقدّم؟')).toBeTruthy();
  });

  it('still does not show it for a goal the backend never enabled (announce has no reward blank)', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    // reward_loyal redeems an EXISTING balance — a different mechanic, correctly excluded.
    expect(screen.queryByText('ماذا تقدّم؟')).toBeNull();
  });
});

// ── the single-item quick-reply button, missing from the phone entirely before this fix ────────
const BOOKINGS_AND_ASSISTANT = {
  checked: true, message: '', apps: [],
  keys: ['feature.bookings', 'feature.whatsapp'],
} as never;

describe('the phone preview now shows the single-item quick-reply button', () => {
  it('shows it for a non-booking goal with exactly one item scoped and both entitlements owned', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}}
                  initialGoalId="reward_loyal" owned={BOOKINGS_AND_ASSISTANT} />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(screen.getByText('معاينة')).toBeTruthy());
    expect(screen.getByText('احجز الآن')).toBeTruthy();
  });

  it('never shows it with more than one item scoped', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}}
                  initialGoalId="reward_loyal" owned={BOOKINGS_AND_ASSISTANT} />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'تلميع كامل' }));
    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(screen.getByText('معاينة')).toBeTruthy());
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });

  it('never shows it without the AI assistant app, bookings alone is not enough', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal"
                  owned={{ checked: true, message: '', apps: [], keys: ['feature.bookings'] } as never} />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(screen.getByText('معاينة')).toBeTruthy());
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });

  it('never shows it without any entitlement wired at all', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}} initialGoalId="reward_loyal" />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(screen.getByText('معاينة')).toBeTruthy());
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });

  it('shows the booking Flow button instead, never both, for a booking goal with bookings owned', async () => {
    render(<Launch session={session} catalog={catalog} onDone={() => {}}
                  initialGoalId="service_offer" owned={BOOKINGS_AND_ASSISTANT} />);
    await waitFor(() => expect(screen.getByText('على أي خدمة؟')).toBeTruthy());
    fireEvent.click(screen.getByRole('button', { name: 'غسلة سريعة' }));
    const amountBox = document.querySelector('input[type="number"]') as HTMLInputElement;
    fireEvent.change(amountBox, { target: { value: '20' } });
    const dateBox = document.querySelector('input[type="date"]') as HTMLInputElement;
    fireEvent.change(dateBox, { target: { value: '2030-01-01' } });
    fireEvent.click(screen.getByRole('button', { name: 'عرض ما سيصل' }));
    await waitFor(() => expect(screen.getByText('معاينة')).toBeTruthy());
    expect(screen.getByText('احجز موعدك الآن')).toBeTruthy();
    expect(screen.queryByText('احجز الآن')).toBeNull();
  });
});
