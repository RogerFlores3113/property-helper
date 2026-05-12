/**
 * URL safety helpers — ASVS V12 + open-redirect mitigation (T-03-09, T-03-10).
 *
 * Scraped strings (source_url, photo_url, posted_date) flow from untrusted
 * upstream HTML into the rendered DOM. These helpers gate which strings are
 * allowed to become <a href> / <img src> targets.
 */

export function isAllowedCraigslistUrl(url: string): boolean {
  try {
    const u = new URL(url);
    const host = u.hostname;
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
    return host === 'craigslist.org' || host.endsWith('.craigslist.org');
  } catch {
    return false;
  }
}

export function isAllowedCraigslistImage(url: string): boolean {
  try {
    const u = new URL(url);
    const host = u.hostname;
    if (u.protocol !== 'https:' && u.protocol !== 'http:') return false;
    return (
      host === 'craigslist.org' ||
      host.endsWith('.craigslist.org') ||
      host.endsWith('craigslistimages.org') ||
      host.endsWith('craigslistimages')
    );
  } catch {
    return false;
  }
}

/**
 * Format an ISO date string as "Mon DD" (current year) or "Mon DD, YYYY" (prior
 * years). Returns the suffix only; caller wraps in `data from {suffix}`.
 */
export function formatPostedDate(iso: string | null): string {
  if (!iso) return 'unknown date';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return 'unknown date';
  const now = new Date();
  const sameYear = d.getUTCFullYear() === now.getUTCFullYear();
  const opts: Intl.DateTimeFormatOptions = sameYear
    ? { month: 'short', day: 'numeric', timeZone: 'UTC' }
    : { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' };
  return new Intl.DateTimeFormat('en-US', opts).format(d);
}
