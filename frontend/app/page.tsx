'use client';

import { useEffect, useRef, useState } from 'react';
import type { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import type { Listing, JobStatus, SearchJob, JobResponse, JobPostPayload } from './types';
import { SearchForm } from './components/SearchForm';

const LOCALSTORAGE_KEY = 'property_helper_job_id';
const API_URL = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
const UUID_RE =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type UiStatus = JobStatus | 'idle' | 'resuming';

function mergeById(prev: Listing[], next: Listing[]): Listing[] {
  const seen = new Set(prev.map((l) => l.id));
  const merged = [...prev];
  for (const l of next) {
    if (!seen.has(l.id)) {
      seen.add(l.id);
      merged.push(l);
    }
  }
  return merged;
}

export default function Home() {
  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<UiStatus>('idle');
  const [listings, setListings] = useState<Listing[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [resumed, setResumed] = useState<boolean>(false);
  const channelRef = useRef<RealtimeChannel | null>(null);

  function subscribe(id: string): RealtimeChannel {
    // Tear down any prior channel before creating a new one (Pitfall 7).
    if (channelRef.current) {
      supabase.removeChannel(channelRef.current);
      channelRef.current = null;
    }
    const ch = supabase.channel(`listings:${id}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'listings',
          filter: `job_id=eq.${id}`,
        },
        (payload: { new: Listing }) => {
          setListings((prev) => mergeById(prev, [payload.new]));
        },
      )
      .on(
        'postgres_changes',
        {
          event: 'UPDATE',
          schema: 'public',
          table: 'search_jobs',
          filter: `id=eq.${id}`,
        },
        (payload: { new: SearchJob }) => {
          const next = payload.new.status;
          setStatus(next);
          if (next !== 'pending') {
            setResumed(false);
          }
        },
      )
      .subscribe();
    channelRef.current = ch;
    return ch;
  }

  async function reattach(id: string) {
    setJobId(id);
    setResumed(true);
    setStatus('resuming');
    try {
      const res = await fetch(`${API_URL}/api/jobs/${id}`);
      if (res.status === 404) {
        localStorage.removeItem(LOCALSTORAGE_KEY);
        setJobId(null);
        setResumed(false);
        setStatus('idle');
        return;
      }
      if (!res.ok) {
        setError(
          "Couldn't start the search. Check that the backend and Redis are running, then try again.",
        );
        setStatus('idle');
        return;
      }
      const body = (await res.json()) as JobResponse;
      if (body.job) {
        setStatus(body.job.status);
      }
      setListings(body.listings ?? []);
      // Subscribe AFTER GET so initial state seeds first, then dedupe via mergeById.
      subscribe(id);
    } catch {
      setError(
        "Couldn't start the search. Check that the backend and Redis are running, then try again.",
      );
      setStatus('idle');
    }
  }

  useEffect(() => {
    const saved = typeof window !== 'undefined'
      ? localStorage.getItem(LOCALSTORAGE_KEY)
      : null;
    if (saved && UUID_RE.test(saved)) {
      void reattach(saved);
    }
    return () => {
      if (channelRef.current) {
        supabase.removeChannel(channelRef.current);
        channelRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function startSearch(payload: JobPostPayload) {
    setError(null);
    setListings([]);
    setResumed(false);
    setStatus('pending');
    try {
      const res = await fetch(`${API_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: payload.query,
          chips: payload.chips,
          global_flex: payload.global_flex,
        }),
      });
      if (!res.ok) {
        setError(
          "Couldn't start the search. Check that the backend and Redis are running, then try again.",
        );
        setStatus('idle');
        setJobId(null);
        return;
      }
      const body = (await res.json()) as { job_id: string; status: JobStatus };
      localStorage.setItem(LOCALSTORAGE_KEY, body.job_id);
      setJobId(body.job_id);
      setResumed(false);
      // Subscribe first, then pull-on-connect to catch any INSERTs that raced
      // ahead of the channel becoming active.
      subscribe(body.job_id);
      try {
        const catchup = await fetch(`${API_URL}/api/jobs/${body.job_id}`);
        if (catchup.ok) {
          const cb = (await catchup.json()) as JobResponse;
          if (cb.listings?.length) setListings((prev) => mergeById(prev, cb.listings));
          if (cb.job?.status) setStatus(cb.job.status);
        }
      } catch { /* non-fatal — Realtime will fill in any gaps */ }
    } catch {
      setError(
        "Couldn't start the search. Check that the backend and Redis are running, then try again.",
      );
      setStatus('idle');
      setJobId(null);
    }
  }

  const inFlight = status === 'pending' || status === 'running' || status === 'resuming';

  function statusBadgeText(): string {
    if (status === 'pending' || status === 'resuming') return 'Queued — searching soon…';
    if (status === 'running') return 'Searching — listings will appear below';
    if (status === 'completed') {
      const n = listings.length;
      return `Done — ${n} listing${n === 1 ? '' : 's'} found`;
    }
    if (status === 'failed') return 'Search failed — try again';
    return '';
  }

  function safeHostname(u: string): string {
    try {
      return new URL(u).hostname;
    } catch {
      return u;
    }
  }

  const showEmpty = !jobId && listings.length === 0 && !error;
  const showCompletedEmpty =
    status === 'completed' && listings.length === 0;

  // Newest first.
  const renderedListings = [...listings].reverse();

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-[720px] px-6 pt-8 pb-12">
        <h1 className="text-[20px] font-semibold leading-tight">
          Property Helper
        </h1>
        <p className="text-sm text-zinc-500 mt-2">
          Describe what you&apos;re looking for. Results stream in automatically.
        </p>

        {resumed && jobId && (
          <div className="mt-6 rounded bg-zinc-100 p-2 text-sm">
            Resumed previous search. Status: {status}.
          </div>
        )}

        {error && (
          <div className="mt-6 rounded border border-red-600 bg-red-50 p-2 text-sm text-red-700" role="alert">
            {error}
          </div>
        )}

        <div className="mt-6">
          <SearchForm onSubmit={startSearch} inFlight={inFlight} />
        </div>

        {jobId && (
          <div
            className="mt-4 inline-block rounded bg-zinc-100 px-3 py-1 text-sm font-semibold"
            aria-live="polite"
          >
            {statusBadgeText()}
          </div>
        )}

        {showCompletedEmpty && (
          <div className="mt-6 rounded bg-zinc-100 p-2 text-sm">
            Search finished with no listings. Check worker logs or try a different query.
          </div>
        )}

        {listings.length > 0 && (
          <ul className="mt-6 flex flex-col gap-4" aria-live="polite">
            {renderedListings.map((l) => (
              <li key={l.id} className="rounded bg-zinc-100 p-2 text-sm">
                <div>
                  <span className="font-semibold">Address</span>: {l.data.address}
                </div>
                <div>
                  <span className="font-semibold">Price</span>: $
                  {l.data.price?.toLocaleString() ?? '—'}
                </div>
                <div>
                  <span className="font-semibold">Beds</span>: {l.data.beds}
                </div>
                <div>
                  <span className="font-semibold">Baths</span>: {l.data.baths}
                </div>
                <div>
                  <span className="font-semibold">Amenities</span>:{' '}
                  {l.data.amenities.join(', ')}
                </div>
                <div>
                  <span className="font-semibold">Source</span>:{' '}
                  <a
                    href={l.data.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="underline"
                  >
                    {safeHostname(l.data.source_url)}
                  </a>
                </div>
                <div>
                  <span className="font-semibold">Posted</span>: {l.data.posted_date}
                </div>
              </li>
            ))}
          </ul>
        )}

        {showEmpty && (
          <div className="mt-8 rounded bg-zinc-100 px-6 py-6 text-center">
            <div className="font-semibold">Describe your ideal apartment</div>
            <div className="mt-1 text-sm">
              Type what you&apos;re looking for above — beds, location, price, amenities. No follow-up questions.
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
