/**
 * The plate formatter — because a wrong rule here splits one car into two customers.
 */
import { describe, expect, it } from 'vitest';
import { formatPlate } from './Visit';

describe('formatPlate', () => {
  it('places the separator so he never types it', () => {
    expect(formatPlate('1234ABC')).toBe('1234 ABC');
  });

  it('accepts a short plate, because a short plate is a real plate', () => {
    expect(formatPlate('12')).toBe('12');
    expect(formatPlate('12A')).toBe('12 A');
  });

  it('holds the Saudi maximum: four digits, three letters', () => {
    expect(formatPlate('123456ABCDE')).toBe('1234 ABC');
  });

  it('drops stray characters rather than refusing the whole entry', () => {
    // A workshop tablet's keyboard produces these, and a box that rejects everything over one of
    // them is a box the operator fights on every car.
    expect(formatPlate('12-34 /a b c')).toBe('1234 ABC');
  });

  it('uppercases, because two scripts for one car is two customers', () => {
    expect(formatPlate('1234abc')).toBe('1234 ABC');
  });
});
