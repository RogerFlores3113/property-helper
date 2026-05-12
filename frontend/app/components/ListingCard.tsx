'use client';

import React, { useCallback } from 'react';
import type { Listing } from '../types';
import {
  isAllowedCraigslistUrl,
  isAllowedCraigslistImage,
  formatPostedDate,
} from './safeUrl';

type Props = {
  listing: Listing;
  hovered: boolean;
  selected: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  registerRef?: (id: string, el: HTMLLIElement | null) => void;
};

function ListingCardImpl({
  listing,
  hovered,
  selected,
  onHover,
  onSelect,
  registerRef,
}: Props) {
  const id = listing.id;
  const data = listing.data;
  const ringClass =
    hovered || selected ? 'ring-2 ring-zinc-900' : 'ring-0';

  const handleEnter = useCallback(() => onHover(id), [id, onHover]);
  const handleLeave = useCallback(() => onHover(null), [onHover]);
  const handleClick = useCallback(() => onSelect(id), [id, onSelect]);
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLLIElement>) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        onSelect(id);
      }
    },
    [id, onSelect]
  );

  const photoOk =
    listing.photo_url && isAllowedCraigslistImage(listing.photo_url);
  const sourceOk = isAllowedCraigslistUrl(data.source_url);
  const topAmenities = data.amenities.slice(0, 3);

  return (
    <li
      role="listitem"
      tabIndex={0}
      aria-current={selected ? 'true' : undefined}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      ref={(el) => registerRef?.(id, el)}
      className={`rounded border border-zinc-200 bg-white p-4 cursor-pointer outline-none ${ringClass} focus-visible:ring-2 focus-visible:ring-zinc-900`}
    >
      <div className="flex justify-between items-baseline gap-3">
        <div className="flex-1 min-w-0">
          {data.address ? (
            <div className="text-sm font-semibold truncate">{data.address}</div>
          ) : (
            <em className="text-sm text-zinc-400 italic">Address unavailable</em>
          )}
        </div>
        <div className="text-sm font-semibold whitespace-nowrap">
          {data.price != null ? `$${data.price.toLocaleString()}` : 'Price not listed'}
        </div>
        {photoOk && (
          <img
            src={listing.photo_url as string}
            alt=""
            className="w-10 h-10 rounded object-cover bg-zinc-100"
          />
        )}
      </div>

      <div className="text-sm text-zinc-700 mt-2">
        {data.beds != null ? `${data.beds} bed` : '— bed'}
        {' · '}
        {data.baths != null ? `${data.baths} bath` : '— bath'}
      </div>

      {topAmenities.length > 0 && (
        <div className="text-xs text-zinc-500 mt-1">
          {topAmenities.join(' · ')}
        </div>
      )}

      <div className="flex items-center justify-between mt-2 text-sm text-zinc-500">
        <span>
          {sourceOk ? (
            <a
              href={data.source_url}
              target="_blank"
              rel="noreferrer"
              className="underline hover:text-zinc-900"
              aria-label={`Open ${data.address ?? 'listing'} on craigslist (new tab)`}
              onClick={(e) => e.stopPropagation()}
            >
              {data.source_name || 'craigslist'} ↗
            </a>
          ) : (
            <span>{data.source_name || 'craigslist'}</span>
          )}
        </span>
        <span className="text-zinc-500">
          data from {formatPostedDate(data.posted_date)}
        </span>
      </div>
    </li>
  );
}

// Custom comparator (Pitfall 8): re-render only when hover/select/id changes.
export const ListingCard = React.memo(ListingCardImpl, (prev, next) => {
  return (
    prev.listing.id === next.listing.id &&
    prev.hovered === next.hovered &&
    prev.selected === next.selected &&
    prev.listing === next.listing
  );
});
