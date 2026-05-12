import { vi } from 'vitest';
import '@testing-library/jest-dom/vitest';

// Global mocks for Next.js server-only modules so server-side modules
// (Server Components, route handlers) import cleanly under jsdom.
// Individual tests can override these per-file with vi.mock() if needed.

vi.mock('next/headers', () => ({
  cookies: async () => ({
    getAll: () => [],
    get: () => undefined,
    set: () => {},
    delete: () => {},
  }),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
    refresh: vi.fn(),
    replace: vi.fn(),
  }),
  redirect: vi.fn(),
}));
