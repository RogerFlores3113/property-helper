import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ListingList } from '../app/components/ListingList';
import type { Listing } from '../app/types';

function makeListing(overrides: Partial<Listing['data']> & { id?: string } = {}): Listing {
  const { id = 'l1', ...data } = overrides;
  return {
    id,
    job_id: 'job-1',
    data: {
      address: 'addr',
      price: 1000,
      beds: 1,
      baths: 1,
      amenities: [],
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

describe('ListingList (MAP-02)', () => {
  it('renders all listings including ones with null coords', () => {
    render(
      <ListingList
        listings={[
          makeListing({ id: 'a' }),
          makeListing({ id: 'b', lat: null, lng: null }),
          makeListing({ id: 'c' }),
        ]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        status="running"
      />
    );
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
  });

  it('shows no-coords notice when some listings lack coords', () => {
    render(
      <ListingList
        listings={[
          makeListing({ id: 'a' }),
          makeListing({ id: 'b', lat: null, lng: null }),
          makeListing({ id: 'c' }),
        ]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        status="running"
      />
    );
    const status = screen.getByRole('status');
    expect(status).toHaveTextContent(/2 of 3 listings have map data/);
  });

  it('renders empty-completed copy when status=completed and no listings', () => {
    render(
      <ListingList
        listings={[]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
        status="completed"
      />
    );
    expect(
      screen.getByText(/Search finished with no listings/i)
    ).toBeInTheDocument();
  });
});
