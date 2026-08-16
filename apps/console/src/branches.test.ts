/**
 * Why «الفروع» is locked, when it is — the two reasons that were one (هـ-3).
 *
 * The tab was locked on whether the caller holds `operations.list_branches` and explained with
 * «الفروع متاحة في باقة أعلى». A role fact under a plan sentence, wrong in both directions: the
 * owner whose plan allows one branch holds that capability on every plan, so he saw no lock and
 * met the refusal only after typing a name; and an employee who simply lacks the permission was
 * told his shop had to pay more, which is a claim about money nobody checked.
 */
import { describe, expect, it } from 'vitest';
import { branchGate } from './branches';

describe('branchGate', () => {
  it('names the PERSON when the person may not read the list', () => {
    expect(branchGate(false, -1)).toBe('role');
    // Even on a plan that allows many. His role is the reason, and there is nothing to sell him.
    expect(branchGate(false, 12)).toBe('role');
    // AND EVEN ON THE BASE PLAN. «باقة أعلى» to somebody who cannot act on it either way sends an
    // employee to ask his owner for money instead of for a permission.
    expect(branchGate(false, 1)).toBe('role');
  });

  it('names the PLAN only when billing said one branch', () => {
    expect(branchGate(true, 1)).toBe('plan');
  });

  it('opens for a shop that may have more than one', () => {
    expect(branchGate(true, 3)).toBe('open');
  });

  it('never locks on an answer we do not have', () => {
    // -1 is «no known ceiling»: an unlimited plan AND a billing we could not reach both land
    // here, because `allows_one_more` fails open by design (services/operations/core/seats.py).
    expect(branchGate(true, -1)).toBe('open');
    // And undefined is a read still in flight, or one that carried no limit at all.
    expect(branchGate(true, undefined)).toBe('open');
  });
});
