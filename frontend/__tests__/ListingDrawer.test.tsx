import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ListingDrawer } from '../app/components/ListingDrawer';
import type { Listing } from '../app/types';

function makeListing(overrides: Partial<Listing['data']> & { id?: string; photo_url?: string | null } = {}): Listing {
  const { id = 'l1', photo_url = null, ...data } = overrides;
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
    photo_url,
    created_at: '2026-05-09T00:00:00Z',
  };
}

describe('ListingDrawer (MAP-04)', () => {
  it('is closed when listing=null (aria-hidden or translate-x-full)', () => {
    render(<ListingDrawer listing={null} onClose={vi.fn()} />);
    const aside = screen.getByRole('dialog', { hidden: true });
    // Either aria-hidden=true OR class contains translate-x-full
    const ariaHidden = aside.getAttribute('aria-hidden');
    const className = aside.className;
    expect(ariaHidden === 'true' || /translate-x-full/.test(className)).toBe(true);
  });

  it('open: renders fields including photo placeholder when photo_url null', () => {
    render(
      <ListingDrawer
        listing={makeListing({ photo_url: null })}
        onClose={vi.fn()}
      />
    );
    expect(screen.getByText('No photo')).toBeInTheDocument();
    expect(screen.getByText(/\$2,500/)).toBeInTheDocument();
    expect(screen.getByText('123 Main St')).toBeInTheDocument();
    expect(screen.getByText(/w\/d/)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: /View on craigslist/i });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noreferrer'));
    expect(screen.getByText(/data from May 9/)).toBeInTheDocument();
  });

  it('renders craigslist link only for craigslist-whitelisted source_url', () => {
    render(
      <ListingDrawer
        listing={makeListing({ source_url: 'https://evil.com/x' })}
        onClose={vi.fn()}
      />
    );
    expect(
      screen.queryByRole('link', { name: /View on craigslist/i })
    ).not.toBeInTheDocument();
  });

  it('close button triggers onClose', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ListingDrawer listing={makeListing()} onClose={onClose} />);
    await user.click(screen.getByRole('button', { name: /Close listing details/i }));
    expect(onClose).toHaveBeenCalled();
  });

  it('Escape key triggers onClose when open', async () => {
    const user = userEvent.setup();
    const onClose = vi.fn();
    render(<ListingDrawer listing={makeListing()} onClose={onClose} />);
    await user.keyboard('{Escape}');
    expect(onClose).toHaveBeenCalled();
  });
});
