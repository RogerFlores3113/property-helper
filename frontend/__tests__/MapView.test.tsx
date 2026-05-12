import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import type { Listing } from '../app/types';

// Shared mock map instance — methods are vi.fn() spies tests inspect by call args.
const mapMock = {
  addSource: vi.fn(),
  addLayer: vi.fn(),
  getSource: vi.fn(() => ({ setData: vi.fn(), getClusterExpansionZoom: vi.fn() })),
  setFeatureState: vi.fn(),
  setData: vi.fn(),
  remove: vi.fn(),
  easeTo: vi.fn(),
  once: vi.fn(),
  on: vi.fn(),
  isStyleLoaded: vi.fn(() => true),
  fitBounds: vi.fn(),
  getCanvas: vi.fn(() => ({ style: { cursor: '' } })),
};

// Reset the source's setData on each test so we can assert call args.
let sourceSetData: ReturnType<typeof vi.fn>;

vi.mock('maplibre-gl', () => {
  return {
    default: {
      Map: vi.fn(() => mapMock),
      LngLatBounds: vi.fn(function (this: { extend: (c: unknown) => unknown }) {
        this.extend = vi.fn(() => this);
        return this;
      }),
    },
    Map: vi.fn(() => mapMock),
    LngLatBounds: vi.fn(function (this: { extend: (c: unknown) => unknown }) {
      this.extend = vi.fn(() => this);
      return this;
    }),
  };
});

vi.mock('maplibre-gl/dist/maplibre-gl.css', () => ({}));

import { MapView } from '../app/components/MapView';

function listing(overrides: Partial<Listing['data']> & { id?: string } = {}): Listing {
  const { id = 'l1', ...data } = overrides;
  return {
    id,
    job_id: 'job-1',
    data: {
      address: '123 Main St',
      price: 2500,
      beds: 2,
      baths: 1,
      amenities: ['w/d'],
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

beforeEach(() => {
  vi.clearAllMocks();
  sourceSetData = vi.fn();
  (mapMock.getSource as unknown as { mockImplementation: (fn: () => unknown) => void }).mockImplementation(() => ({
    setData: sourceSetData,
    getClusterExpansionZoom: vi.fn(async () => 14),
  }));
  // Default: trigger the 'load' callback synchronously so addSource runs.
  // Use a plain reassignment to sidestep TS variance on mockImplementation
  // (mapMock.on is typed as Mock<Procedure | Constructable> due to shape inference).
  (mapMock.on as unknown as { mockImplementation: (fn: (...a: unknown[]) => unknown) => void }).mockImplementation(
    (event: unknown, ...args: unknown[]) => {
      if (event === 'load' && typeof args[0] === 'function') {
        (args[0] as () => void)();
      }
    }
  );
});

describe('MapView (MAP-01, MAP-02)', () => {
  it('addSource is called with cluster:true + clusterRadius:50 + clusterMaxZoom:14', () => {
    render(
      <MapView
        listings={[listing()]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    const call = mapMock.addSource.mock.calls.find((c) => c[0] === 'listings');
    expect(call).toBeDefined();
    expect(call![1]).toMatchObject({
      cluster: true,
      clusterRadius: 50,
      clusterMaxZoom: 14,
    });
  });

  it('setData filters out listings with null coords', () => {
    render(
      <MapView
        listings={[
          listing({ id: 'a' }),
          listing({ id: 'b', lat: null, lng: null }),
          listing({ id: 'c' }),
        ]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    // setData was called with a FeatureCollection containing 2 features (a and c).
    expect(sourceSetData).toHaveBeenCalled();
    const lastCall = sourceSetData.mock.calls[sourceSetData.mock.calls.length - 1];
    const fc = lastCall[0] as { features: unknown[] };
    expect(fc.features).toHaveLength(2);
  });

  it('unmount calls map.remove', () => {
    const { unmount } = render(
      <MapView
        listings={[listing()]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    unmount();
    expect(mapMock.remove).toHaveBeenCalled();
  });

  it('setFeatureState is called on hover and select changes (including clear-previous)', () => {
    const { rerender } = render(
      <MapView
        listings={[listing({ id: 'listing-x' }), listing({ id: 'listing-y' })]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );

    // Hover on listing-x.
    rerender(
      <MapView
        listings={[listing({ id: 'listing-x' }), listing({ id: 'listing-y' })]}
        hoveredId="listing-x"
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    expect(mapMock.setFeatureState).toHaveBeenCalledWith(
      { source: 'listings', id: 'listing-x' },
      { hovered: true }
    );

    // Move hover to null — should clear previous (listing-x, hovered:false).
    rerender(
      <MapView
        listings={[listing({ id: 'listing-x' }), listing({ id: 'listing-y' })]}
        hoveredId={null}
        selectedId={null}
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    expect(mapMock.setFeatureState).toHaveBeenCalledWith(
      { source: 'listings', id: 'listing-x' },
      { hovered: false }
    );

    // Select listing-y.
    rerender(
      <MapView
        listings={[listing({ id: 'listing-x' }), listing({ id: 'listing-y' })]}
        hoveredId={null}
        selectedId="listing-y"
        onHover={vi.fn()}
        onSelect={vi.fn()}
      />
    );
    expect(mapMock.setFeatureState).toHaveBeenCalledWith(
      { source: 'listings', id: 'listing-y' },
      { selected: true }
    );
  });
});
