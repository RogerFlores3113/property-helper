import { describe, it, expect } from 'vitest';
import {
  isAllowedCraigslistImage,
  isAllowedApartmentsUrl,
} from '../app/components/safeUrl';

describe('safeUrl — CR-02 regression (D-22)', () => {
  it('rejects an attacker-controlled host that happens to end with "craigslistimages"', () => {
    // The pre-fix code used host.endsWith("craigslistimages") which would
    // accept "evilcraigslistimages.org". Must reject.
    expect(
      isAllowedCraigslistImage('https://evilcraigslistimages.org/foo.jpg')
    ).toBe(false);
  });

  it('accepts the legitimate images subdomain', () => {
    expect(
      isAllowedCraigslistImage('https://images.craigslistimages.org/foo.jpg')
    ).toBe(true);
  });

  it('accepts the apex craigslistimages.org host', () => {
    expect(
      isAllowedCraigslistImage('https://craigslistimages.org/foo.jpg')
    ).toBe(true);
  });

  it('still accepts craigslist.org subdomain images', () => {
    expect(
      isAllowedCraigslistImage('https://images.craigslist.org/foo.jpg')
    ).toBe(true);
  });

  it('rejects non-http(s) protocols', () => {
    expect(isAllowedCraigslistImage('javascript:alert(1)')).toBe(false);
  });
});

describe('safeUrl — isAllowedApartmentsUrl (D-23 / T-04-03)', () => {
  it('accepts the apex apartments.com', () => {
    expect(isAllowedApartmentsUrl('https://apartments.com/listing/123')).toBe(
      true
    );
  });

  it('accepts www.apartments.com', () => {
    expect(
      isAllowedApartmentsUrl('https://www.apartments.com/listing/123')
    ).toBe(true);
  });

  it('rejects an attacker-controlled host that ends with "apartments.com" suffix-fooling', () => {
    expect(
      isAllowedApartmentsUrl('https://evilapartments.com/listing/123')
    ).toBe(false);
  });

  it('rejects javascript: protocol', () => {
    expect(isAllowedApartmentsUrl('javascript:alert(1)')).toBe(false);
  });

  it('rejects an unparseable string', () => {
    expect(isAllowedApartmentsUrl('not a url')).toBe(false);
  });

  it('rejects http (non-https?) — actually accepts both http and https per pattern', () => {
    // Mirroring isAllowedCraigslistUrl which accepts both http and https.
    expect(isAllowedApartmentsUrl('http://apartments.com/x')).toBe(true);
  });
});
