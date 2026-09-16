/**
 * `plan.requires_any` — نقاطي needs a touchpoint app (تسجيل زيارة or الحجوزات) already active,
 * data-driven off plans.json, same posture `services/operations/app/core/subscribe.py::may_add`
 * reads it with. These are the pure-function tests; the purchase refusal itself is tested there.
 */
import { describe, expect, it } from 'vitest';
import { missingRequirement, planLines, requiresAny, type Plan } from './billingShared';
import type { Owned } from './apps';

function loyaltyPlan(): Plan {
  return {
    id: 'p_loyalty',
    name: 'برنامج النقاط',
    limits: {
      'feature.loyalty': { kind: 'boolean', limit: 1 },
      'plan.requires_any': { kind: 'list', list: ['feature.visit', 'feature.bookings'] } as never,
    },
  };
}

function owned(keys: string[]): Owned {
  return { checked: true, message: '', keys, apps: [] };
}

describe('requiresAny', () => {
  it('reads the dependency list straight off the plan row', () => {
    expect(requiresAny(loyaltyPlan())).toEqual(['feature.visit', 'feature.bookings']);
  });

  it('is empty for a plan with no `plan.requires_any` key at all', () => {
    expect(requiresAny({ id: 'p', name: 'x', limits: { 'feature.campaigns': { kind: 'boolean', limit: 1 } } }))
      .toEqual([]);
  });
});

describe('missingRequirement', () => {
  it('names both apps when neither dependency is held', () => {
    const note = missingRequirement(loyaltyPlan(), owned([]));
    expect(note).toContain('تسجيل زيارة');
    expect(note).toContain('الحجوزات');
  });

  it('is empty once either dependency is held', () => {
    expect(missingRequirement(loyaltyPlan(), owned(['feature.visit']))).toBe('');
    expect(missingRequirement(loyaltyPlan(), owned(['feature.bookings']))).toBe('');
  });

  it('is empty while the read has not settled — never flashes a lock it cannot justify', () => {
    expect(missingRequirement(loyaltyPlan(), undefined)).toBe('');
    expect(missingRequirement(loyaltyPlan(), null)).toBe('');
  });

  it('is empty for a plan with no dependency declared', () => {
    const plan: Plan = { id: 'p', name: 'x', limits: { 'feature.campaigns': { kind: 'boolean', limit: 1 } } };
    expect(missingRequirement(plan, owned([]))).toBe('');
  });
});

describe('plan.requires_any never prints as a plan line', () => {
  it('is invisible on the card itself — the note lives beside the buy button, not in the list', () => {
    const lines = planLines(loyaltyPlan());
    expect(lines.some((l) => l.includes('requires_any'))).toBe(false);
  });
});
