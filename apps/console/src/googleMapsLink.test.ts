import { describe, expect, it } from 'vitest';
import { isShortGoogleMapsLink, parseGoogleMapsLink } from './googleMapsLink';

describe('parseGoogleMapsLink', () => {
  it('reads the @lat,lng shape from a panned/zoomed map URL', () => {
    const url = 'https://www.google.com/maps/@24.7136,46.6753,17z';
    expect(parseGoogleMapsLink(url)).toEqual({ lat: 24.7136, lng: 46.6753 });
  });

  it('reads a full place link with the @lat,lng segment before /data=', () => {
    const url = 'https://www.google.com/maps/place/Some+Place/@21.5433,39.1728,15z/data=!3m1!4b1';
    expect(parseGoogleMapsLink(url)).toEqual({ lat: 21.5433, lng: 39.1728 });
  });

  it('reads the ?q=lat,lng shape from a dropped-pin share', () => {
    const url = 'https://maps.google.com/?q=24.7136,46.6753';
    expect(parseGoogleMapsLink(url)).toEqual({ lat: 24.7136, lng: 46.6753 });
  });

  it('reads the ?ll=lat,lng shape', () => {
    const url = 'https://maps.google.com/maps?ll=21.5433,39.1728&z=14';
    expect(parseGoogleMapsLink(url)).toEqual({ lat: 21.5433, lng: 39.1728 });
  });

  it('reads the !3d!4d shape embedded in a place link data blob', () => {
    const url = 'https://www.google.com/maps/place/x/data=!4m5!3m4!1s0x0!8m2!3d24.7136!4d46.6753';
    expect(parseGoogleMapsLink(url)).toEqual({ lat: 24.7136, lng: 46.6753 });
  });

  it('prefers the @lat,lng pattern over a coincidental match later in the same URL', () => {
    const url = 'https://www.google.com/maps/@24.7136,46.6753,17z/data=!3d99!4d99';
    expect(parseGoogleMapsLink(url)).toEqual({ lat: 24.7136, lng: 46.6753 });
  });

  it('returns null for a short link — it carries no coordinates to parse', () => {
    expect(parseGoogleMapsLink('https://maps.app.goo.gl/AbCd1234')).toBeNull();
    expect(parseGoogleMapsLink('https://goo.gl/maps/AbCd1234')).toBeNull();
  });

  it('returns null for empty, whitespace, or unrelated text', () => {
    expect(parseGoogleMapsLink('')).toBeNull();
    expect(parseGoogleMapsLink('   ')).toBeNull();
    expect(parseGoogleMapsLink('ليس رابطاً')).toBeNull();
  });

  it('refuses an out-of-range coordinate rather than returning a wrong point', () => {
    expect(parseGoogleMapsLink('https://maps.google.com/?q=200,46.6753')).toBeNull();
  });
});

describe('isShortGoogleMapsLink', () => {
  it('recognises both real short-link hosts', () => {
    expect(isShortGoogleMapsLink('https://maps.app.goo.gl/AbCd1234')).toBe(true);
    expect(isShortGoogleMapsLink('https://goo.gl/maps/AbCd1234')).toBe(true);
    expect(isShortGoogleMapsLink('https://www.goo.gl/maps/AbCd1234')).toBe(true);
  });

  it('is false for a full maps.google.com link', () => {
    expect(isShortGoogleMapsLink('https://www.google.com/maps/@24.7136,46.6753,17z')).toBe(false);
  });

  it('is false for garbage that is not even a URL', () => {
    expect(isShortGoogleMapsLink('ليس رابطاً')).toBe(false);
  });
});
