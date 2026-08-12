/**
 * The two sentences on this page that were wrong for the customer an owner opens most often.
 */
import { describe, expect, it } from 'vitest';
import { ago } from './Customer';
import { asLocal as local } from '../phone';

describe('local', () => {
  it('shows the number the way he knows it, not the way the network stores it', () => {
    expect(local('966573579663')).toBe('0573579663');
  });

  it('leaves an already-local number alone', () => {
    expect(local('0549491771')).toBe('0549491771');
  });
});

describe('ago', () => {
  it('says «اليوم» rather than «قبل 0 يوماً» — nobody says that', () => {
    expect(ago(0, true)).toBe('اليوم');
  });

  it('has words for one and two, because Arabic does', () => {
    expect(ago(1, true)).toBe('أمس');
    expect(ago(2, true)).toBe('قبل يومين');
  });

  it('switches from أيام to يوماً at eleven, as the language does', () => {
    expect(ago(9, true)).toBe('قبل 9 أيام');
    expect(ago(30, true)).toBe('قبل 30 يوماً');
  });

  it('never invents a date for a customer with no visit', () => {
    expect(ago(0, false)).toBe('—');
  });
});
