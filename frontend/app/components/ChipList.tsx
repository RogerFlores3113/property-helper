'use client';

import { useRef, useState } from 'react';
import type { Chip, ChipType } from '../types';

export type ChipListProps = {
  chips: Chip[];
  onUpdate: (id: string, patch: Partial<Chip>) => void;
  onRemove: (id: string) => void;
  onToggleFlex: (id: string) => void;
  onAdd: (chip: Chip) => void;
};

function chipLabel(chip: Chip): string {
  switch (chip.type) {
    case 'beds':
      return `${chip.value}BR`;
    case 'max_price':
      return `$${Number(chip.value).toLocaleString()} max`;
    case 'min_price':
      return `$${Number(chip.value).toLocaleString()} min`;
    case 'baths':
      return `${chip.value} bath`;
    case 'amenity':
      return String(chip.value);
    case 'location':
      return String(chip.value);
    default:
      return String(chip.value);
  }
}

type ChipPillProps = {
  chip: Chip;
  onUpdate: (id: string, patch: Partial<Chip>) => void;
  onRemove: (id: string) => void;
  onToggleFlex: (id: string) => void;
};

function ChipPill({ chip, onUpdate, onRemove, onToggleFlex }: ChipPillProps) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(String(chip.value));
  const removeIntentRef = useRef(false);

  function confirm() {
    if (removeIntentRef.current) {
      removeIntentRef.current = false;
      onRemove(chip.id);
    } else if (draft.trim()) {
      onUpdate(chip.id, { value: draft.trim() });
    } else {
      onRemove(chip.id);
    }
    setEditing(false);
  }

  const flexClass = chip.flex
    ? 'border-dashed border-zinc-400 bg-zinc-100'
    : 'border-zinc-200 bg-zinc-100';

  if (editing) {
    return (
      <li className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 border-zinc-300 bg-white`}>
        <input
          type="text"
          value={draft}
          autoFocus
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault();
              e.stopPropagation();
              confirm();
            } else if (e.key === 'Escape') {
              e.preventDefault();
              e.stopPropagation();
              setEditing(false);
            }
          }}
          onBlur={confirm}
          className="text-sm outline-none bg-transparent min-w-[80px]"
        />
        <button
          type="button"
          aria-label={`Remove ${chipLabel(chip)} filter`}
          onMouseDown={() => { removeIntentRef.current = true; }}
          className="ml-1 text-xs text-zinc-500 hover:text-zinc-800"
        >
          ×
        </button>
      </li>
    );
  }

  return (
    <li className={`inline-flex items-center gap-1 rounded-full border px-3 py-1 text-sm font-semibold ${flexClass}`}>
      <button
        type="button"
        className="bg-transparent p-0 text-left"
        onClick={() => { setDraft(String(chip.value)); setEditing(true); }}
      >
        {chipLabel(chip)}
      </button>
      <button
        type="button"
        aria-label={`Toggle flex for ${chipLabel(chip)}`}
        aria-pressed={chip.flex}
        onClick={() => onToggleFlex(chip.id)}
        className="ml-1 text-xs text-zinc-500 hover:text-zinc-800"
      >
        ~
      </button>
      <button
        type="button"
        aria-label={`Remove ${chipLabel(chip)} filter`}
        onClick={() => onRemove(chip.id)}
        className="ml-1 text-xs text-zinc-500 hover:text-zinc-800"
      >
        ×
      </button>
    </li>
  );
}

function AddFilterForm({ onAdd }: { onAdd: (chip: Chip) => void }) {
  const [type, setType] = useState<ChipType>('beds');
  const [value, setValue] = useState('');
  const [flex, setFlex] = useState(false);

  function commit() {
    if (!value.trim()) return;
    onAdd({ id: crypto.randomUUID(), type, value: value.trim(), flex });
    setValue('');
    setFlex(false);
  }

  return (
    <li className="inline-flex items-center gap-1 text-sm">
      <select
        value={type}
        onChange={(e) => setType(e.target.value as ChipType)}
        className="rounded border border-zinc-300 px-1 py-0.5 text-sm"
      >
        <option value="beds">beds</option>
        <option value="baths">baths</option>
        <option value="max_price">max price</option>
        <option value="min_price">min price</option>
        <option value="amenity">amenity</option>
        <option value="location">location</option>
      </select>
      <input
        type="text"
        placeholder="value"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commit(); }
        }}
        className="rounded border border-zinc-300 px-1 py-0.5 text-sm w-24"
      />
      <label className="flex items-center gap-1 text-xs text-zinc-500">
        <input type="checkbox" checked={flex} onChange={(e) => setFlex(e.target.checked)} />
        flex
      </label>
      <button
        type="button"
        onClick={commit}
        className="rounded bg-zinc-900 px-2 py-0.5 text-xs text-white"
      >
        Add
      </button>
    </li>
  );
}

export function ChipList({ chips, onUpdate, onRemove, onToggleFlex, onAdd }: ChipListProps) {
  const [showAdd, setShowAdd] = useState(false);

  function handleAdd(chip: Chip) {
    onAdd(chip);
    setShowAdd(false);
  }

  return (
    <ul role="list" className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <ChipPill
          key={chip.id}
          chip={chip}
          onUpdate={onUpdate}
          onRemove={onRemove}
          onToggleFlex={onToggleFlex}
        />
      ))}
      {showAdd ? (
        <AddFilterForm onAdd={handleAdd} />
      ) : (
        <li>
          <button
            type="button"
            onClick={() => setShowAdd(true)}
            className="inline-flex items-center gap-1 rounded-full border border-dashed border-zinc-300 px-3 py-1 text-sm text-zinc-500 hover:border-zinc-400 hover:text-zinc-700"
          >
            + Add filter
          </button>
        </li>
      )}
    </ul>
  );
}
