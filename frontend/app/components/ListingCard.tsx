'use client';

import React, { useCallback } from 'react';
import type { Listing } from '../types';
import {
  isAllowedCraigslistUrl,
  isAllowedCraigslistImage,
  isAllowedSourceUrl,
  formatPostedDate,
} from './safeUrl';

type Props = {
  listing: Listing;
  hovered: boolean;
  selected: boolean;
  onHover: (id: string | null) => void;
  onSelect: (id: string) => void;
  registerRef?: (id: string, el: HTMLLIElement | null) => void;
  onExtend?: (id: string) => void | Promise<void>;
  onResearch?: (id: string) => void | Promise<void>;
};

function ListingCardImpl({
  listing,
  hovered,
  selected,
  onHover,
  onSelect,
  registerRef,
  onExtend,
  onResearch,
}: Props) {
  const id = listing.id;
  const data = listing.data;
  const ringClass =
    hovered || selected ? 'ring-2 ring-zinc-900' : 'ring-0';

  // CACH-02: amber stale label + Extend/Re-search controls appear when
  // listing.expires_at has fallen behind wall-clock. Comparator below
  // covers expires_at so the row re-renders after a successful Extend.
  const isStale = listing.expires_at
    ? new Date(listing.expires_at).getTime() <= Date.now()
    : false;

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

  const handleExtendClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation();
      if (onExtend) void onExtend(id);
    },
    [id, onExtend]
  );
  const handleResearchClick = useCallback(
    (e: React.MouseEvent<HTMLButtonElement>) => {
      e.stopPropagation();
      if (onResearch) void onResearch(id);
    },
    [id, onResearch]
  );

  const photoOk =
    listing.photo_url && isAllowedCraigslistImage(listing.photo_url);
  const sourceOk = isAllowedCraigslistUrl(data.source_url);
  const topAmenities = data.amenities.slice(0, 3);

  // SCRAP-08: merged-source rendering when >=2 sources_list entries pass
  // the per-source host whitelist. Falls back to the single existing
  // source link below the date row.
  const sourcesList = data.sources_list ?? [];
  const safeSources = sourcesList.filter((s) =>
    isAllowedSourceUrl(s.source_name, s.source_url)
  );
  const showSourcesList = safeSources.length >= 2;

  const labelClass = isStale ? 'text-amber-600' : 'text-zinc-500';
  const labelText = `data from ${formatPostedDate(data.posted_date)}${isStale ? ' — expired' : ''}`;

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
        <span className={labelClass}>{labelText}</span>
      </div>

      {showSourcesList && (
        <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-zinc-500">
          {safeSources.map((s, i) => (
            <li key={`${s.source_name}-${i}`}>
              <a
                href={s.source_url}
                target="_blank"
                rel="noreferrer"
                className="underline hover:text-zinc-900"
                aria-label={`Open ${data.address ?? 'listing'} on ${s.source_name} (new tab)`}
                onClick={(e) => e.stopPropagation()}
              >
                {s.source_name} ↗
              </a>
            </li>
          ))}
        </ul>
      )}

      {isStale && (onExtend || onResearch) && (
        <div className="mt-2 flex gap-3 text-sm">
          {onExtend && (
            <button
              type="button"
              onClick={handleExtendClick}
              aria-label={`Extend listing ${data.address ?? listing.id}`}
              className="underline text-zinc-700 hover:text-zinc-900"
            >
              Extend
            </button>
          )}
          {onResearch && (
            <button
              type="button"
              onClick={handleResearchClick}
              aria-label={`Re-search ${data.address ?? listing.id}`}
              className="underline text-zinc-700 hover:text-zinc-900"
            >
              Re-search
            </button>
          )}
        </div>
      )}
    </li>
  );
}

// Custom comparator (Pitfall 8): re-render only when hover/select/id changes,
// or when expires_at / sources_list change (so a successful Extend or a
// dedup-induced sources_list merge propagates visually).
export const ListingCard = React.memo(ListingCardImpl, (prev, next) => {
  return (
    prev.listing.id === next.listing.id &&
    prev.hovered === next.hovered &&
    prev.selected === next.selected &&
    prev.listing === next.listing &&
    prev.listing.expires_at === next.listing.expires_at &&
    prev.listing.data.sources_list === next.listing.data.sources_list
  );
});
