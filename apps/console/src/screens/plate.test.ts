/**
 * The plate formatter — because a wrong rule here splits one car into two customers.
 */
import { describe, expect, it } from 'vitest';
import { formatPlate } from './Visit';
import { asLocal } from '../phone';

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

describe('asLocal', () => {
  it('turns what the server stores into what the screen validates', () => {
    // THE BUG THIS NAMES: the plate lookup filled «966555555555», the validator wanted
    // «05XXXXXXXX», and «حفظ وإرسال» stayed dead with a perfectly good customer on the page.
    expect(asLocal('966555555555')).toBe('0555555555');
  });

  it('leaves a local number alone, so a typed number is never rewritten under him', () => {
    expect(asLocal('0501234567')).toBe('0501234567');
  });

  it('matches the validator this screen uses', () => {
    expect(/^05\d{8}$/.test(asLocal('966501234567'))).toBe(true);
  });
});
