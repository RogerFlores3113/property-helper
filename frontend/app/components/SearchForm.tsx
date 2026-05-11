'use client';

import { useMemo, useState } from 'react';
import type { Chip, JobPostPayload } from '../types';
import { parseQuery } from '../../lib/parseQuery';
import { ChipList } from './ChipList';

export type SearchFormProps = {
  inFlight: boolean;
  onSubmit: (payload: JobPostPayload) => void;
};

export function SearchForm({ inFlight, onSubmit }: SearchFormProps) {
  const [query, setQuery] = useState<string>('');
  const [globalFlex, setGlobalFlex] = useState<boolean>(false);
  const [overrides, setOverrides] = useState<Chip[]>([]);
  const [edits, setEdits] = useState<Record<string, Partial<Chip>>>({});
  const [removed, setRemoved] = useState<Set<string>>(new Set());
  const [flexed, setFlexed] = useState<Set<string>>(new Set());

  const chips = useMemo<Chip[]>(() => {
    const parsed = parseQuery(query);
    const merged = [...parsed, ...overrides];
    return merged
      .filter((c) => !removed.has(c.id))
      .map((c) => {
        const patch = edits[c.id];
        const value = patch?.value !== undefined ? patch.value : c.value;
        const flex = flexed.has(c.id) ? !c.flex : c.flex;
        return { ...c, value, flex };
      });
  }, [query, overrides, edits, removed, flexed]);

  function handleUpdate(id: string, patch: Partial<Chip>) {
    setEdits((prev) => ({ ...prev, [id]: { ...(prev[id] ?? {}), ...patch } }));
  }

  function handleRemove(id: string) {
    setRemoved((prev) => {
      const next = new Set(prev);
      next.add(id);
      return next;
    });
  }

  function handleToggleFlex(id: string) {
    setFlexed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inFlight) return;
    onSubmit({ query, chips, global_flex: globalFlex });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <textarea
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        disabled={inFlight}
        placeholder="e.g. 2BR in SF Bay Area under $5000 with in-unit W/D"
        rows={3}
        className="w-full rounded border border-zinc-300 p-2 text-sm disabled:bg-zinc-100 disabled:cursor-not-allowed"
      />

      <div className="flex items-center gap-2">
        <button
          type="button"
          role="switch"
          aria-checked={globalFlex}
          aria-label="willing to flex"
          onClick={() => setGlobalFlex((v) => !v)}
          className={`inline-flex h-6 w-11 items-center rounded-full transition ${
            globalFlex ? 'bg-amber-500' : 'bg-zinc-300'
          }`}
        >
          <span
            className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
              globalFlex ? 'translate-x-5' : 'translate-x-0.5'
            }`}
          />
        </button>
        <span className="text-sm text-zinc-700">Willing to flex on these</span>
      </div>

      {chips.length > 0 && (
        <ChipList
          chips={chips}
          onUpdate={handleUpdate}
          onRemove={handleRemove}
          onToggleFlex={handleToggleFlex}
        />
      )}

      <button
        type="submit"
        disabled={inFlight}
        className="self-start rounded bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {inFlight ? 'Searching…' : 'Start search'}
      </button>
    </form>
  );
}
