import { describe, expect, it } from 'vitest';
import { waDigits, waLink } from './whatsapp';

describe('waDigits', () => {
  it('normalizes a local 05… number to 966…', () => {
    expect(waDigits('0501234567')).toBe('966501234567');
  });

  it('accepts an already-E.164 966… number as-is', () => {
    expect(waDigits('966501234567')).toBe('966501234567');
  });

  it('accepts a bare 9-digit mobile (no leading 0)', () => {
    expect(waDigits('501234567')).toBe('966501234567');
  });

  it('folds Arabic-Indic digits before recognizing the number', () => {
    expect(waDigits('0501234567')).toBe('966501234567');
  });

  it('refuses an empty or unrecognizable number rather than guessing', () => {
    expect(waDigits('')).toBeNull();
    expect(waDigits('12345')).toBeNull();
  });
});

describe('waLink', () => {
  it('builds a plain wa.me link with no text', () => {
    expect(waLink('0501234567')).toBe('https://wa.me/966501234567');
  });

  it('URL-encodes the pre-filled text', () => {
    expect(waLink('0501234567', 'مرحباً!')).toBe(
      'https://wa.me/966501234567?text=%D9%85%D8%B1%D8%AD%D8%A8%D8%A7%D9%8B!');
  });

  it('returns null for an unrecognizable number, text or not', () => {
    expect(waLink('not-a-number', 'hi')).toBeNull();
  });
});
