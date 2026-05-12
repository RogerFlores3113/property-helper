import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ListingCard } from '../app/components/ListingCard';
import type { Listing } from '../app/types';

function makeListing(overrides: Partial<Listing['data']> & { id?: string } = {}): Listing {
  const { id = 'l1', ...data } = overrides;
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
});
