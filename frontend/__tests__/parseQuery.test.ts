import { describe, it, expect } from 'vitest';
import { parseQuery } from '../lib/parseQuery';
import type { Chip } from '../app/types';

describe('parseQuery (SRCH-01)', () => {
  it('canonical: 2BR in Champaign under $1500 with in-unit W/D produces beds, max_price, location, amenity chips', () => {
    const chips = parseQuery('2BR in Champaign under $1500 with in-unit W/D');

    const beds = chips.find((c: Chip) => c.type === 'beds');
    expect(beds).toBeDefined();
    expect(beds?.value).toBe(2);

    const maxPrice = chips.find((c: Chip) => c.type === 'max_price');
    expect(maxPrice).toBeDefined();
    expect(maxPrice?.value).toBe(1500);

    const location = chips.find((c: Chip) => c.type === 'location');
    expect(location).toBeDefined();
    expect(location?.value).toBe('Champaign');

    const amenity = chips.find((c: Chip) => c.type === 'amenity');
    expect(amenity).toBeDefined();
  });

  it('returns [] for queries shorter than 5 characters', () => {
    expect(parseQuery('2BR')).toEqual([]);
  });

  it('price range $1000-$2000 produces both min_price and max_price chips', () => {
    const chips = parseQuery('apartment $1000-$2000 in Austin');

    const minPrice = chips.find((c: Chip) => c.type === 'min_price');
    const maxPrice = chips.find((c: Chip) => c.type === 'max_price');

    expect(minPrice).toBeDefined();
    expect(minPrice?.value).toBe(1000);
    expect(maxPrice).toBeDefined();
    expect(maxPrice?.value).toBe(2000);
  });

  it('strips stop words from location: "in Champaign" -> "Champaign"', () => {
    const chips = parseQuery('2BR in Champaign under $1500');
    const location = chips.find((c: Chip) => c.type === 'location');
    expect(location?.value).toBe('Champaign');
  });

  it('coerces numeric chip values to number type, not string', () => {
    const chips = parseQuery('2BR in Champaign under $1500');
    const beds = chips.find((c: Chip) => c.type === 'beds');
    const maxPrice = chips.find((c: Chip) => c.type === 'max_price');
    expect(typeof beds?.value).toBe('number');
    expect(beds?.value).toBe(2);
    expect(typeof maxPrice?.value).toBe('number');
    expect(maxPrice?.value).toBe(1500);
  });
});
