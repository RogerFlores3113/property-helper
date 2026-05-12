import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ListingCard } from '../app/components/ListingCard';
import type { Listing } from '../app/types';

function makeListing(
  overrides: Partial<Listing['data']> & {
    id?: string;
    expires_at?: string;
  } = {}
): Listing {
  const { id = 'l1', expires_at, ...data } = overrides;
  return {
    id,
    job_id: 'job-1',
    data: {
      address: '123 Main St',
      price: 2500,
      beds: 2,
      baths: 1,
      amenities: ['w/d', 'parking', 'pet ok'],
      source_url: 'https://sfbay.craigslist.org/apa/x.html',
      posted_date: '2026-05-09',
      lat: 37.78,
      lng: -122.4,
      source_name: 'craigslist',
      ...data,
    },
    photo_url: null,
    created_at: '2026-05-09T00:00:00Z',
    // Default: fresh (1 day in the future) so existing tests don't flip into
    // stale-state. Tests that need stale pass expires_at explicitly.
    expires_at:
      expires_at ?? new Date(Date.now() + 24 * 3600 * 1000).toISOString(),
  };
}

describe('ListingCard (MAP-03)', () => {
  it('renders MAP-03 fields', () => {
    render(
      <ListingCard
        listing={makeListing()}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    expect(screen.getByText('123 Main St')).toBeInTheDocument();
    expect(screen.getByText(/\$2,500/)).toBeInTheDocument();
    expect(screen.getByText(/2 bed/)).toBeInTheDocument();
    expect(screen.getByText(/1 bath/)).toBeInTheDocument();
    expect(screen.getByText(/craigslist/i)).toBeInTheDocument();
    expect(screen.getByText(/data from May 9/)).toBeInTheDocument();
  });

  it('renders address fallback when null', () => {
    render(
      <ListingCard
        listing={makeListing({ address: null })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    const el = screen.getByText('Address unavailable');
    expect(el).toBeInTheDocument();
    expect(el.tagName.toLowerCase()).toBe('em');
  });

  it('hover callbacks fire on mouse enter and leave', async () => {
    const user = userEvent.setup();
    const onHover = vi.fn();
    render(
      <ListingCard
        listing={makeListing({ id: 'abc' })}
        hovered={false}
        selected={false}
        onHover={onHover}
        onSelect={vi.fn()}
      />
    );
    const li = screen.getByRole('listitem');
    await user.hover(li);
    expect(onHover).toHaveBeenCalledWith('abc');
    await user.unhover(li);
    expect(onHover).toHaveBeenCalledWith(null);
  });

  it('click triggers onSelect', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ListingCard
        listing={makeListing({ id: 'abc' })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={onSelect}
      />
    );
    await user.click(screen.getByRole('listitem'));
    expect(onSelect).toHaveBeenCalledWith('abc');
  });

  it('applies hover ring class when hovered=true', () => {
    render(
      <ListingCard
        listing={makeListing()}
        hovered={true}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    const li = screen.getByRole('listitem');
    expect(li.className).toMatch(/ring-2/);
    expect(li.className).toMatch(/ring-zinc-900/);
  });

  it('keyboard Enter triggers onSelect', async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(
      <ListingCard
        listing={makeListing({ id: 'kb' })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={onSelect}
      />
    );
    const li = screen.getByRole('listitem');
    li.focus();
    await user.keyboard('{Enter}');
    expect(onSelect).toHaveBeenCalledWith('kb');
  });

  // ---- Phase 5 (CACH-02 / SCRAP-08) additions ----

  it('renders amber expired label when expires_at is in the past', () => {
    const past = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    render(
      <ListingCard
        listing={makeListing({ expires_at: past })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        onExtend={vi.fn()}
        onResearch={vi.fn()}
      />
    );
    const label = screen.getByText(/expired/);
    expect(label).toBeInTheDocument();
    expect(label.className).toMatch(/text-amber-600/);
  });

  it('renders zinc label and no Extend/Re-search buttons when fresh', () => {
    const future = new Date(Date.now() + 24 * 3600 * 1000).toISOString();
    render(
      <ListingCard
        listing={makeListing({ expires_at: future })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        onExtend={vi.fn()}
        onResearch={vi.fn()}
      />
    );
    const label = screen.getByText(/data from/);
    expect(label.className).toMatch(/text-zinc-500/);
    expect(label.textContent).not.toMatch(/expired/);
    expect(screen.queryByRole('button', { name: /Extend/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Re-search/ })).toBeNull();
  });

  it('Extend button invokes onExtend with id', async () => {
    const user = userEvent.setup();
    const past = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    const onExtend = vi.fn();
    render(
      <ListingCard
        listing={makeListing({ id: 'ex1', expires_at: past })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        onExtend={onExtend}
      />
    );
    await user.click(screen.getByRole('button', { name: /Extend/ }));
    expect(onExtend).toHaveBeenCalledWith('ex1');
  });

  it('Re-search button invokes onResearch with id', async () => {
    const user = userEvent.setup();
    const past = new Date(Date.now() - 24 * 3600 * 1000).toISOString();
    const onResearch = vi.fn();
    render(
      <ListingCard
        listing={makeListing({ id: 'rs1', expires_at: past })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        onResearch={onResearch}
      />
    );
    await user.click(screen.getByRole('button', { name: /Re-search/ }));
    expect(onResearch).toHaveBeenCalledWith('rs1');
  });

  it('sources_list renders multiple whitelisted links', () => {
    render(
      <ListingCard
        listing={makeListing({
          sources_list: [
            { source_name: 'craigslist', source_url: 'https://sfbay.craigslist.org/apa/x.html' },
            { source_name: 'apartments', source_url: 'https://www.apartments.com/p/123' },
          ],
        })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    // The primary source link still renders ("craigslist ↗") plus the two
    // sources_list anchors. Assert both sources_list entries are linked.
    const apt = screen.getByRole('link', { name: /apartments/i });
    expect(apt).toBeInTheDocument();
    expect(apt.getAttribute('href')).toBe('https://www.apartments.com/p/123');
    // At least 2 craigslist matches (primary + sources_list entry).
    const allLinks = screen.getAllByRole('link');
    expect(allLinks.length).toBeGreaterThanOrEqual(2);
  });

  it('sources_list filters disallowed hosts', () => {
    render(
      <ListingCard
        listing={makeListing({
          sources_list: [
            { source_name: 'craigslist', source_url: 'https://evil.example.com/x' },
            { source_name: 'apartments', source_url: 'https://www.apartments.com/p/ok' },
          ],
        })}
        hovered={false}
        selected={false}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    // Only one safe source remains → list does NOT render (showSourcesList
    // requires >= 2 passing). So neither "evil" nor a sources_list <ul>
    // should be present.
    expect(screen.queryByText(/evil\.example\.com/)).toBeNull();
    // The single safe apartments entry won't render in the multi-link list
    // (length < 2), so no apartments link should appear from sources_list.
    // (Primary source_url is craigslist, so no apartments link at all.)
    expect(screen.queryByRole('link', { name: /apartments/i })).toBeNull();
  });
});
