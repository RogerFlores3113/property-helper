'use client';

import { useState } from 'react';
import type { Chip } from '../types';

export type ChipListProps = {
  chips: Chip[];
  onUpdate: (id: string, patch: Partial<Chip>) => void;
  onRemove: (id: string) => void;
  onToggleFlex: (id: string) => void;
};

function chipLabel(chip: Chip): string {
  switch (chip.type) {
    case 'beds':
      return `${chip.value}BR`;
    case 'baths':
      return `${chip.value}BA`;
    case 'min_price':
      return `>$${Number(chip.value).toLocaleString()}`;
    case 'max_price':
      return `<$${Number(chip.value).toLocaleString()}`;
    case 'amenity':
      return String(chip.value);
    case 'location':
      return String(chip.value);
    default:
      return String(chip.value);
  }
}

export function ChipList({ chips, onUpdate, onRemove, onToggleFlex }: ChipListProps) {
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<string>('');

  function startEdit(chip: Chip) {
    setEditingId(chip.id);
    setDraft(String(chip.value));
  }

  function commitEdit(id: string) {
    onUpdate(id, { value: draft });
    setEditingId(null);
    setDraft('');
  }

  function cancelEdit() {
    setEditingId(null);
    setDraft('');
  }

  return (
    <ul className="flex flex-wrap gap-2" aria-label="search chips">
      {chips.map((chip) => {
        const isEditing = editingId === chip.id;
        return (
          <li
            key={chip.id}
            className={`inline-flex items-center gap-1 rounded-full border px-2 py-1 text-sm ${
              chip.flex ? 'border-amber-500 bg-amber-50' : 'border-zinc-300 bg-zinc-50'
            }`}
          >
            {isEditing ? (
              <input
                type="text"
                value={draft}
                autoFocus
                onChange={(e) => setDraft(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault();
                    commitEdit(chip.id);
                  } else if (e.key === 'Escape') {
                    e.preventDefault();
                    cancelEdit();
                  }
                }}
                onBlur={() => commitEdit(chip.id)}
                className="w-20 rounded border border-zinc-300 px-1 py-0.5 text-sm"
              />
            ) : (
              <button
                type="button"
                className="cursor-text bg-transparent p-0 text-left"
                onClick={() => startEdit(chip)}
              >
                {chipLabel(chip)}
              </button>
            )}
            <button
              type="button"
              aria-label={`toggle flex ${chip.id}`}
              aria-pressed={chip.flex}
              onClick={() => onToggleFlex(chip.id)}
              className="ml-1 rounded px-1 text-xs text-zinc-600 hover:bg-zinc-200"
            >
              ~
            </button>
            <button
              type="button"
              aria-label={`remove ${chip.id}`}
              onClick={() => onRemove(chip.id)}
              className="ml-1 rounded px-1 text-xs text-zinc-600 hover:bg-zinc-200"
            >
              ×
            </button>
          </li>
        );
      })}
    </ul>
  );
}
