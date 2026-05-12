# Phase 4 Plan 04 (D-09): Playwright-capable backend image.
#
# Switches from a plain python:3.12 base (~150 MB) to the official Microsoft
# Playwright Python image (~1.5 GB) so headless Chromium binaries are present
# for run_search_apartments. The image size delta is intentional and unavoidable
# for Apartments.com via Playwright + playwright-stealth.
#
# Pinned to playwright 1.59 to match backend/pyproject.toml; Pitfall 9 of
# 04-RESEARCH.md: this image bundles Chromium but NOT the playwright Python
# package — `uv sync` installs it from pyproject.
FROM mcr.microsoft.com/playwright/python:v1.59.0-jammy

WORKDIR /app

# Install uv (project's package manager) before copying source.
RUN pip install --no-cache-dir uv

# Copy lockfile + manifest first so dependency layer is cached across source edits.
COPY pyproject.toml uv.lock ./

# Install dependencies into a project venv (--no-dev: production-only).
RUN uv sync --no-dev --frozen

# Pitfall 9 verification step: ensure the playwright Python package is now
# importable inside the venv (the base image's bundled Chromium binaries are
# useless without the python bindings).
RUN uv run python -c "from playwright.async_api import async_playwright; print('playwright ok')"

# Copy application sources last so source edits don't bust the dependency layer.
COPY app ./app

# ARQ worker entrypoint — coordinator + craigslist + apartments sub-tasks.
CMD ["uv", "run", "arq", "app.workers.settings.WorkerSettings"]
