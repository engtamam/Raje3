/**
 * A wording's standing is READ, never inferred — and «we could not ask» draws nothing.
 *
 * WHAT THIS IS WRITTEN AFTER. The preview showed one sentence for three unrelated states: «القوالب
 * تُراجَع لدى واتساب، وقد تستغرق ساعات» appeared when our own library could not be read, when we
 * simply ship no wording for that reason, and when his own text was genuinely waiting at Meta.
 * Two of those three are ours, and Meta is not involved in either — so an owner sat waiting for a
 * review that was not happening, about texts WhatsApp never sees.
 *
 * THE HARD HALF IS THE FOURTH STATE. `approved` arrives as `null` when notification-service could
 * not be asked. Rendering that as «بانتظار اعتماد واتساب» would be the same defect one row
 * smaller: a verdict we never received, printed as one. So it draws no badge at all.
 */
import { describe, expect, it } from 'vitest';
import { standing } from './MessagePreview';

describe('what a wording says about itself', () => {
  it('says it is ready only when the account actually holds the approval', () => {
    expect(standing({ name: 'a', tone: 'brief', text: 't', approved: true })?.label)
      .toBe('جاهزة للإرسال');
  });

  it('says it is waiting when the account does NOT hold it', () => {
    expect(standing({ name: 'a', tone: 'brief', text: 't', approved: false })?.label)
      .toBe('بانتظار اعتماد واتساب');
  });

  it('says NOTHING when we could not ask', () => {
    // The whole point. `null` is «not known», and not-known is not a verdict.
    expect(standing({ name: 'a', tone: 'brief', text: 't', approved: null })).toBeNull();
    expect(standing({ name: 'a', tone: 'brief', text: 't' })).toBeNull();
  });

  it('carries Meta\'s refusal on his own text rather than hiding the row', () => {
    // It used to be filtered out entirely: a text he wrote and Meta refused simply vanished, with
    // no wording, no reason, and nothing to fix.
    const s = standing({ name: 'mine', tone: '', text: 't', mine: true, status: 'rejected' });
    expect(s?.label).toBe('رفضها واتساب');
    expect(s?.tone).toBe('danger');
  });

  it('tells a text he never submitted from one Meta is holding', () => {
    expect(standing({ name: 'm', tone: '', text: 't', mine: true, status: 'draft' })?.label)
      .toBe('لم تُرفَع بعد');
    expect(standing({ name: 'm', tone: '', text: 't', mine: true, status: 'pending' })?.label)
      .toBe('عند واتساب للمراجعة');
  });
});
