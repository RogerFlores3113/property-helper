'use client';

import { useEffect, useRef, useState } from 'react';
import type { RealtimeChannel } from '@supabase/supabase-js';
import { supabase } from '@/lib/supabase';
import type { Listing, JobStatus, SearchJob, JobResponse, JobPostPayload } from './types';
import { SearchForm } from './components/SearchForm';
import { MapView } from './components/MapView';
import { ListingList } from './components/ListingList';
import { ListingDrawer } from './components/ListingDrawer';

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
  const [currentJob, setCurrentJob] = useState<SearchJob | null>(null);
  const [status, setStatus] = useState<UiStatus>('idle');
  const [listings, setListings] = useState<Listing[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [resumed, setResumed] = useState<boolean>(false);
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
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
        setCurrentJob(body.job);
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

  // CACH-02: PATCH /api/listings/{id}/extend; on 200 splice new expires_at
  // into local state via the same mergeById/replace pattern used elsewhere.
  async function handleExtend(listingId: string): Promise<void> {
    try {
      const res = await fetch(`${API_URL}/api/listings/${listingId}/extend`, {
        method: 'PATCH',
      });
      if (!res.ok) {
        console.error('extend failed', res.status);
        return;
      }
      const body = (await res.json()) as { id: string; expires_at: string };
      setListings((prev) =>
        prev.map((l) =>
          l.id === body.id ? { ...l, expires_at: body.expires_at } : l
        )
      );
    } catch (err) {
      console.error('extend error', err);
    }
  }

  // SCRAP-08 / CACH-01: POST /api/jobs again with the original chips so the
  // cache-hit fast-path may serve a fresh copy. If chips weren't persisted
  // (older Phase-4 job), prompt the user to re-enter the query.
  async function handleResearch(_listingId: string): Promise<void> {
    if (!currentJob || !currentJob.chips || currentJob.chips.length === 0) {
      window.alert(
        'This search predates Phase 5 — please re-enter your query in the search box above.'
      );
      return;
    }
    try {
      const res = await fetch(`${API_URL}/api/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: currentJob.query,
          chips: currentJob.chips,
          global_flex: false,
        }),
      });
      if (!res.ok) {
        console.error('re-search failed', res.status);
        return;
      }
      const body = (await res.json()) as { job_id: string; status: JobStatus };
      localStorage.setItem(LOCALSTORAGE_KEY, body.job_id);
      // Reload the page so reattach() pulls the new job cleanly (mirrors the
      // fire-and-forget pattern; Phase 7 dashboard will replace this).
      window.location.reload();
    } catch (err) {
      console.error('re-search error', err);
    }
  }

  async function startSearch(payload: JobPostPayload) {
    setError(null);
    setListings([]);
    setCurrentJob(null);
    setResumed(false);
    setSelectedId(null);
    setHoveredId(null);
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
          if (cb.job) setCurrentJob(cb.job);
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
  // Selected listing (drawer source of truth).
  const selectedListing =
    selectedId != null
      ? (listings.find((l) => l.id === selectedId) ?? null)
      : null;

  // Map list-related UiStatus to ListingList's typed status.
  const listStatus: 'idle' | 'pending' | 'running' | 'completed' | 'failed' | 'resuming' =
    status;

  // Reference safeHostname so an existing helper stays alive for future use
  // (debug surfaces); component code now uses safeUrl helpers instead.
  void safeHostname;

  return (
    <main className="min-h-screen bg-white">
      <div className="mx-auto max-w-[1280px] px-6 pt-8 pb-12">
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

        <div className="mt-6 max-w-[720px]">
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

        {jobId && (
          <div className="mt-6 grid grid-cols-1 md:grid-cols-[3fr_2fr] gap-6 h-[calc(100vh-12rem)]">
            <div className="md:sticky md:top-4 md:h-[calc(100vh-12rem)]">
              <MapView
                listings={listings}
                hoveredId={hoveredId}
                selectedId={selectedId}
                onHover={setHoveredId}
                onSelect={setSelectedId}
              />
            </div>
            <div className="overflow-hidden h-full">
              <ListingList
                listings={listings}
                hoveredId={hoveredId}
                selectedId={selectedId}
                onHover={setHoveredId}
                onSelect={setSelectedId}
                status={listStatus}
                onExtend={handleExtend}
                onResearch={handleResearch}
              />
            </div>
          </div>
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

      <ListingDrawer
        listing={selectedListing}
        onClose={() => setSelectedId(null)}
      />
    </main>
  );
}
