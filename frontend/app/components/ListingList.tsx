'use client';

import { useEffect, useRef } from 'react';
import type { Listing } from '../types';
import { ListingCard } from './ListingCard';

type Props = {
  listings: Listing[];
  hoveredId: string | null;
  selectedId: string | null;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  status: 'idle' | 'pending' | 'running' | 'completed' | 'failed' | 'resuming';
};

export function ListingList({
  listings,
  hoveredId,
  selectedId,
  onHover,
  onSelect,
  status,
}: Props) {
  const cardRefs = useRef<Map<string, HTMLLIElement>>(new Map());

  // D-14: when a pin is hovered (hoveredId changes to non-null), scroll the
  // matching card into view via the callback-ref registry.
  useEffect(() => {
    if (!hoveredId) return;
    const el = cardRefs.current.get(hoveredId);
    el?.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [hoveredId]);

  const registerRef = (id: string, el: HTMLLIElement | null) => {
    if (el) cardRefs.current.set(id, el);
    else cardRefs.current.delete(id);
  };

  const noCoordsCount = listings.filter(
    (l) => l.data.lat == null || l.data.lng == null
  ).length;
  const haveCoordsCount = listings.length - noCoordsCount;

  if (status === 'completed' && listings.length === 0) {
    return (
      <div className="rounded bg-zinc-100 p-4 text-sm text-zinc-700">
        Search finished with no listings. Try a different query or city.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3 h-full">
      {noCoordsCount > 0 && (
        <div
          role="status"
          aria-live="polite"
          className="bg-zinc-100 text-zinc-500 text-sm p-2 rounded"
        >
          {haveCoordsCount} of {listings.length} listings have map data — see the list below.
        </div>
      )}
      <ul
        role="list"
        className="flex flex-col gap-4 overflow-y-auto flex-1 min-h-0"
      >
        {listings.map((l) => (
          <ListingCard
            key={l.id}
            listing={l}
            hovered={hoveredId === l.id}
            selected={selectedId === l.id}
            onHover={onHover}
            onSelect={onSelect}
            registerRef={registerRef}
          />
        ))}
      </ul>
    </div>
  );
}
