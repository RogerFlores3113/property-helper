'use client';

import { useEffect } from 'react';
import type { Listing } from '../types';
import {
  isAllowedCraigslistUrl,
  isAllowedCraigslistImage,
  formatPostedDate,
} from './safeUrl';

type Props = {
  listing: Listing | null;
  onClose: () => void;
};

export function ListingDrawer({ listing, onClose }: Props) {
  const open = listing !== null;

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [open, onClose]);

  // Wrapper is always rendered; closed state slides off-screen and is aria-hidden.
  const positionClass = open ? 'translate-x-0' : 'translate-x-full';

  if (!open) {
    return (
      <aside
        role="dialog"
        aria-modal="false"
        aria-hidden="true"
        aria-labelledby="drawer-title"
        className={`fixed right-0 top-0 h-full w-[420px] bg-white shadow-xl border-l border-zinc-200 transform transition-transform duration-200 ${positionClass}`}
      />
    );
  }

  const data = listing!.data;
  const photoOk =
    listing!.photo_url && isAllowedCraigslistImage(listing!.photo_url);
  const sourceOk = isAllowedCraigslistUrl(data.source_url);

  return (
    <aside
      role="dialog"
      aria-modal="false"
      aria-labelledby="drawer-title"
      className={`fixed right-0 top-0 h-full w-[420px] bg-white shadow-xl border-l border-zinc-200 transform transition-transform duration-200 ${positionClass} flex flex-col`}
    >
      <header className="p-4 border-b border-zinc-200 flex items-center justify-between gap-3">
        <h2
          id="drawer-title"
          className="text-[20px] font-semibold leading-tight truncate"
        >
          {data.address ?? 'Listing details'}
        </h2>
        <button
          type="button"
          aria-label="Close listing details"
          onClick={onClose}
          className="text-zinc-400 hover:text-zinc-900 text-xl leading-none"
        >
          ×
        </button>
      </header>

      <div className="p-4 flex flex-col gap-4 overflow-y-auto">
        {photoOk ? (
          <img
            src={listing!.photo_url as string}
            alt=""
            className="w-full h-48 object-cover rounded bg-zinc-100"
          />
        ) : (
          <div className="w-full h-48 rounded bg-zinc-100 flex items-center justify-center text-zinc-400 text-sm">
            No photo
          </div>
        )}

        <div className="text-[20px] font-semibold">
          {data.price != null ? `$${data.price.toLocaleString()}` : 'Price not listed'}
        </div>

        <div className="grid grid-cols-2 gap-y-2 text-sm">
          <div>
            <span className="text-zinc-500">Beds: </span>
            {data.beds ?? '—'}
          </div>
          <div>
            <span className="text-zinc-500">Baths: </span>
            {data.baths ?? '—'}
          </div>
          {data.amenities.length > 0 && (
            <div className="col-span-2">
              <span className="text-zinc-500">Amenities: </span>
              {data.amenities.join(', ')}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between text-sm">
          <span className="text-zinc-500">{data.source_name || 'craigslist'}</span>
          {sourceOk && (
            <a
              href={data.source_url}
              target="_blank"
              rel="noreferrer"
              className="text-zinc-700 underline hover:text-zinc-900"
            >
              View on craigslist ↗
            </a>
          )}
        </div>

        <div className="text-sm text-zinc-500">
          data from {formatPostedDate(data.posted_date)}
        </div>
      </div>
    </aside>
  );
}
