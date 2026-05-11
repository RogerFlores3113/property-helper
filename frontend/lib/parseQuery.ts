import type { Chip } from '../app/types';

// Regex order is LOAD-BEARING (RESEARCH.md Pitfall 1):
// PRICE_RANGE_RE must execute and consume its substring BEFORE MAX_PRICE_RE
// runs, otherwise "$1000-$2000" trips MAX_PRICE_RE on the second number.
const BEDS_RE = /(\d)\s*(?:BR|br|bd|bed|bedroom)s?/i;
const BATHS_RE = /(\d)\s*(?:ba|bath|baths)/i;
const PRICE_RANGE_RE = /\$(\d[\d,]*)\s*[-–]\s*\$(\d[\d,]*)/;
const MAX_PRICE_RE = /(?:under|<)\s*\$(\d[\d,]*)/i;
const WD_RE = /in-unit\s+w\/?d|in-unit\s+washer/i;
const PARKING_RE = /\bparking\b/i;
const DISHWASHER_RE = /\bdishwasher\b/i;
const PET_RE = /pet.?friendly|pets?\s+ok/i;

// Stop words for location heuristic (RESEARCH.md Pitfall 2)
const STOP_WORDS = /\b(?:in|at|near|with|and|for)\b/gi;

function newId(): string {
  // crypto.randomUUID() is available in Node 24, Chrome 92+, Firefox 95+
  return crypto.randomUUID();
}

function toNumber(s: string): number {
  return parseFloat(s.replace(/,/g, ''));
}

type Consumed = { start: number; end: number };

function consume(consumed: Consumed[], match: RegExpExecArray): void {
  consumed.push({ start: match.index, end: match.index + match[0].length });
}

function stripConsumed(text: string, consumed: Consumed[]): string {
  // Replace consumed ranges with spaces (avoids word collisions)
  const chars = text.split('');
  for (const { start, end } of consumed) {
    for (let i = start; i < end; i++) {
      chars[i] = ' ';
    }
  }
  return chars.join('');
}

export function parseQuery(text: string): Chip[] {
  if (text.trim().length < 5) {
    return [];
  }

  const beds: Chip[] = [];
  const baths: Chip[] = [];
  const minPrice: Chip[] = [];
  const maxPrice: Chip[] = [];
  const amenities: Chip[] = [];
  const consumed: Consumed[] = [];

  const bedsMatch = BEDS_RE.exec(text);
  if (bedsMatch) {
    consume(consumed, bedsMatch);
    beds.push({ id: newId(), type: 'beds', value: parseInt(bedsMatch[1], 10), flex: false });
  }

  const bathsMatch = BATHS_RE.exec(text);
  if (bathsMatch) {
    consume(consumed, bathsMatch);
    baths.push({ id: newId(), type: 'baths', value: parseInt(bathsMatch[1], 10), flex: false });
  }

  // PRICE_RANGE_RE MUST run before MAX_PRICE_RE
  const rangeMatch = PRICE_RANGE_RE.exec(text);
  if (rangeMatch) {
    consume(consumed, rangeMatch);
    minPrice.push({ id: newId(), type: 'min_price', value: toNumber(rangeMatch[1]), flex: false });
    maxPrice.push({ id: newId(), type: 'max_price', value: toNumber(rangeMatch[2]), flex: false });
  } else {
    const maxMatch = MAX_PRICE_RE.exec(text);
    if (maxMatch) {
      consume(consumed, maxMatch);
      maxPrice.push({ id: newId(), type: 'max_price', value: toNumber(maxMatch[1]), flex: false });
    }
  }

  const amenityChecks: Array<[RegExp, string]> = [
    [WD_RE, 'in-unit W/D'],
    [PARKING_RE, 'parking'],
    [DISHWASHER_RE, 'dishwasher'],
    [PET_RE, 'pet-friendly'],
  ];
  for (const [re, label] of amenityChecks) {
    const m = re.exec(text);
    if (m) {
      consume(consumed, m);
      amenities.push({ id: newId(), type: 'amenity', value: label, flex: false });
    }
  }

  // Location: strip consumed ranges, strip stop words, collapse whitespace.
  const stripped = stripConsumed(text, consumed)
    .replace(STOP_WORDS, ' ')
    .replace(/\$\d[\d,]*/g, ' ')
    .replace(/[<>]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim();

  const location: Chip[] = [];
  if (stripped.length >= 2) {
    location.push({ id: newId(), type: 'location', value: stripped, flex: false });
  }

  return [...beds, ...baths, ...minPrice, ...maxPrice, ...amenities, ...location];
}
