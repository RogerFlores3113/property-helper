import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { SearchForm } from '../app/components/SearchForm';

describe('SearchForm (SRCH-03)', () => {
  it('GlobalFlexToggle toggles aria-checked', async () => {
    const user = userEvent.setup();
    render(<SearchForm inFlight={false} onSubmit={vi.fn()} />);
    const toggle = screen.getByRole('switch', { name: /willing to flex/i });
    expect(toggle).toHaveAttribute('aria-checked', 'false');
    await user.click(toggle);
    expect(toggle).toHaveAttribute('aria-checked', 'true');
  });

  it('textarea is disabled when inFlight=true', () => {
    render(<SearchForm inFlight={true} onSubmit={vi.fn()} />);
    expect(screen.getByRole('textbox')).toBeDisabled();
  });
});
