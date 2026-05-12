import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChipList } from '../app/components/ChipList';
import type { Chip } from '../app/types';

function makeChip(overrides: Partial<Chip> = {}): Chip {
  return {
    id: 'test-id',
    type: 'beds',
    value: 2,
    flex: false,
    ...overrides,
  };
}

describe('ChipList (SRCH-02, SRCH-04)', () => {
  it('clicking a chip label enters edit mode', async () => {
    const user = userEvent.setup();
    const chip = makeChip();
    render(
      <ChipList
        chips={[chip]}
        onUpdate={vi.fn()}
        onRemove={vi.fn()}
        onToggleFlex={vi.fn()}
        onAdd={vi.fn()}
      />
    );
    await user.click(screen.getByText('2BR'));
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('pressing Enter in edit input calls onUpdate with the new value', async () => {
    const user = userEvent.setup();
    const onUpdate = vi.fn();
    const chip = makeChip();
    render(
      <ChipList
        chips={[chip]}
        onUpdate={onUpdate}
        onRemove={vi.fn()}
        onToggleFlex={vi.fn()}
        onAdd={vi.fn()}
      />
    );
    await user.click(screen.getByText('2BR'));
    const input = screen.getByRole('textbox') as HTMLInputElement;
    await user.clear(input);
    await user.type(input, '3{Enter}');
    expect(onUpdate).toHaveBeenCalledWith(
      'test-id',
      expect.objectContaining({ value: '3' })
    );
  });

  it('clicking the per-chip flex toggle (~) calls onToggleFlex with chip id', async () => {
    const user = userEvent.setup();
    const onToggleFlex = vi.fn();
    const chip = makeChip();
    render(
      <ChipList
        chips={[chip]}
        onUpdate={vi.fn()}
        onRemove={vi.fn()}
        onToggleFlex={onToggleFlex}
        onAdd={vi.fn()}
      />
    );
    await user.click(screen.getByRole('button', { name: /toggle flex/i }));
    expect(onToggleFlex).toHaveBeenCalledWith('test-id');
  });
});
