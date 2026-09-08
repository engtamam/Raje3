/**
 * `MessagePreview` in TEMPLATE-TYPE mode — reached by a campaign goal with no reasons-registry
 * counterpart at all (announce, awareness, seasonal_care, service_offer, package_offer). Reads
 * `reminders.preview_by_type` instead of `reminders.preview_reason`, and drops everything that
 * only makes sense attached to a reason: his own texts, the switch, retexting.
 */
import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen } from '@testing-library/react';

const calls: { id: string; params: unknown }[] = [];

vi.mock('../catalog', async (importOriginal) => {
  const real = await importOriginal<typeof import('../catalog')>();
  return {
    ...real,
    action: (_c: unknown, id: string) => ({ id, label: id, method: 'GET', path: `/${id}` }),
    call: async (_s: unknown, a: { id: string }, params?: unknown) => {
      calls.push({ id: a.id, params });
      if (a.id === 'reminders.preview_by_type') {
        return {
          options: [{ name: 'mkt_announcement_warm', tone: 'warm',
                     text: 'خبر جديد من محلّك: كذا', mine: false }],
          chosen: '', empty_because: '', tone: 'warm',
        };
      }
      if (a.id === 'reminders.my_template_help') return { requests: [] };
      return {};
    },
  };
});

const { MessagePreview } = await import('./MessagePreview');

afterEach(() => { cleanup(); calls.length = 0; });

const session = {} as never;
const catalog = { services: [], unreachable: [] } as never;

describe('MessagePreview — templateType mode (no reason id)', () => {
  it('reads reminders.preview_by_type by template_type, not preview_reason', async () => {
    render(<MessagePreview session={session} catalog={catalog}
                           templateType="mkt_announcement" label="أعلن جديدك" when="متى شئت"
                           canRetext={false} onClose={() => {}} onChosen={() => {}} />);
    await screen.findByText(/خبر جديد من محلّك/);
    expect(calls.some((c) => c.id === 'reminders.preview_by_type'
      && (c.params as { template_type: string }).template_type === 'mkt_announcement')).toBe(true);
    expect(calls.some((c) => c.id === 'reminders.preview_reason')).toBe(false);
    expect(calls.some((c) => c.id === 'reminders.my_templates')).toBe(false);
  });

  it('never offers to write his own text in this mode — no reason to attach it to', async () => {
    render(<MessagePreview session={session} catalog={catalog}
                           templateType="mkt_announcement" label="أعلن جديدك" when="متى شئت"
                           canRetext={false} onClose={() => {}} onChosen={() => {}} />);
    await screen.findByText(/خبر جديد من محلّك/);
    expect(screen.queryByText('اكتب نصّك')).toBeNull();
    expect(screen.queryByText(/حقٍّ نظامي/)).toBeNull();
  });
});
