'use client';

import { useRef, useState } from 'react';
import type { Chip, JobPostPayload } from '../types';
import { parseQuery } from '../../lib/parseQuery';
import { ChipList } from './ChipList';

type SearchFormProps = {
  inFlight: boolean;
  onSubmit: (payload: JobPostPayload) => void;
};

export function SearchForm({ inFlight, onSubmit }: SearchFormProps) {
  const [query, setQuery] = useState<string>('');
  const [chips, setChips] = useState<Chip[]>([]);
  const [globalFlex, setGlobalFlex] = useState<boolean>(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  function handleChange(e: React.ChangeEvent<HTMLTextAreaElement>) {
    const text = e.target.value;
    setQuery(text);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setChips(text.trim().length < 5 ? [] : parseQuery(text));
    }, 400);
  }

  function handleUpdate(id: string, patch: Partial<Chip>) {
    setChips((prev) => prev.map((c) => (c.id === id ? { ...c, ...patch } : c)));
  }

  function handleRemove(id: string) {
    setChips((prev) => prev.filter((c) => c.id !== id));
  }

  function handleToggleFlex(id: string) {
    setChips((prev) => prev.map((c) => (c.id === id ? { ...c, flex: !c.flex } : c)));
  }

  function handleAdd(chip: Chip) {
    setChips((prev) => [...prev, chip]);
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (inFlight || !query.trim()) return;
    onSubmit({ query, chips, global_flex: globalFlex });
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <textarea
        value={query}
        onChange={handleChange}
        disabled={inFlight}
        autoFocus
        rows={3}
        aria-label="Apartment search query"
        placeholder="e.g. 2BR in SF Bay Area under $5000 with in-unit W/D"
        className="w-full rounded border border-zinc-300 p-2 text-sm disabled:bg-zinc-100 disabled:cursor-not-allowed"
      />

      {chips.length > 0 && (
        <ChipList
          chips={chips}
          onUpdate={handleUpdate}
          onRemove={handleRemove}
          onToggleFlex={handleToggleFlex}
          onAdd={handleAdd}
        />
      )}

      <div className="flex items-center gap-2">
        <button
          type="button"
          role="switch"
          aria-checked={globalFlex}
          aria-label="Willing to flex on constraints"
          onClick={() => setGlobalFlex((v) => !v)}
          className={
            globalFlex
              ? 'rounded-full bg-zinc-900 text-white px-3 py-1 text-sm font-semibold'
              : 'rounded-full border border-zinc-300 px-3 py-1 text-sm text-zinc-500'
          }
        >
          willing to flex
        </button>
      </div>

      <button
        type="submit"
        disabled={inFlight || !query.trim()}
        className="self-start rounded bg-zinc-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {inFlight ? 'Searching…' : 'Search apartments'}
      </button>
    </form>
  );
}
