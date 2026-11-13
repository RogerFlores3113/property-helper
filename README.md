# Property Helper

A helper for your own apartment or house hunt that lives on your own computer: every place you found, where it
stands, what it really costs per month, how well it fits what you want, how long the commute is, who you talked
to and when the tours are. Nothing to sign up for, nothing leaves your computer unless you turn on the map or use
AI.

It is free and open source. It works from its own window in your browser, and Claude (or any MCP client) can add
and update places for you: paste a listing into Claude and say "add this to my search".

## Install

**Paste this repo's link into an assistant that can run commands on your own computer and say "Install".**
That works in the Claude app's **Code** tab or in Cowork on your own computer, in Claude Code, and in Codex. A
plain chat in the Claude app cannot run commands, so use the no-terminal route right below instead. The assistant
reads [INSTALL.md](INSTALL.md), runs the one install script for your computer, checks the download against its
checksum, installs the app and opens it. Your places are kept in a folder of their own, so installing again to
update never touches them.

**No terminal? Download the app instead.** Open this repository's Releases page, download the file for your
computer (`PropertyHelper-mac.zip`, `PropertyHelper-windows.zip` or `PropertyHelper-linux.tar.gz`), unzip it and
double-click Property Helper. On a Mac the first time, right-click (or Control-click) the app, choose **Open**, then
press **Open** again. On Windows, if "Windows protected your PC" appears, press **More info**, then **Run anyway**.
The app is not code-signed yet.

Or run the install line yourself. It is saved to a file first and then run, so a failed download stops with an
error. Mac or Linux, in a terminal:

```sh
curl -fsSL https://raw.githubusercontent.com/rogerflores3113/property-helper/main/install.sh -o "${TMPDIR:-/tmp}/ph-install.sh" && sh "${TMPDIR:-/tmp}/ph-install.sh"
```

Windows, in PowerShell:

```powershell
irm https://raw.githubusercontent.com/rogerflores3113/property-helper/main/install.ps1 | iex
```

The script checks the download against a checksum from the same release. That catches a damaged download, not a
tampered release. Builds exist for Apple silicon Macs, Windows 10 or 11 (64-bit) and Linux (x86_64). While this
repository is private, download the release files from the Releases page and see INSTALL.md for the folder
override (`PROPHELPER_INSTALL_FROM`).

## Run it from the source (about 2 minutes the first time)

1. On this page on GitHub press the green **Code** button, then **Download ZIP**, and unzip it somewhere
   permanent (not Downloads).
2. Double-click **Start Property Helper.command** (Mac, the first time right-click it and choose **Open**) or
   **Start Property Helper.bat** (Windows). It sets itself up, starts the app and opens your browser. Keep that
   window open while you use the app.

Or from a terminal, with [uv](https://docs.astral.sh/uv/) installed:

```sh
uv run prophelper serve        # starts the app and opens your browser (port 8767)
uv run prophelper open         # opens a fresh, unlocked window of the running app
```

If a window says it is **locked**, open Property Helper again from its icon (or run `prophelper open`). The app
only answers requests from this computer, and only from a window the app itself opened.

## What you can do

- **Search**: say whether you are renting or buying, your budget and what matters (price, bedrooms, commute,
  laundry, dishwasher, parking, pets, newer buildings, or your own criteria). Mark must-haves as deal-breakers.
- **Add**: paste a link, the listing text, or both. The price, bedrooms, fees and more are filled in for you to
  check. Property Helper never opens the link itself.
- **Board**: one column per stage (Saved, Contacted, Tour booked, Toured, Applied, Approved, Lease signed,
  Passed; buyers get their own stages). Drag a card or use its menu. Places that fail a deal-breaker are hidden,
  with a link to show them.
- **Place page**: every fact, the true monthly cost with the numbers still missing named, the fit score
  broken down line by line, commute times you can overwrite, the timeline, a note box, archive and delete.
- **Today**: tours this week, people who have not replied, dates coming up and places that are new.
- **Sample data**: a made-up search with 10 places to look around, removable from Settings in one press.

Your own notes are yours: an AI app can add its own notes next to them but never changes or deletes yours, and it
can only move a place forward through the stages, never back.

## Connect an AI app

Open **Connect an AI app** in the app and press **Connect** for the Claude app, Codex or LM Studio, then **Add
skills**. The connection runs `prophelper mcp`, a server that talks to the same data over stdio. It can add and
update places, and it can never delete anything.

## What leaves your computer

Only three things can use the network, and each is yours to control (the Privacy page lists them again):

1. Map tiles, loaded by your browser from OpenStreetMap when the map is shown (Settings can turn tiles off).
2. An opt-in address lookup (default off) through OpenStreetMap Nominatim, at most one request a second.
3. AI calls to Anthropic with your own key, only when you press an AI button.

No telemetry, no analytics, no update checks, no accounts. Your data is one SQLite file plus a files folder in
your data folder (shown in Settings). **Download a backup copy** there now and then.

## For developers

```sh
uv sync --all-groups
uv run pytest -q
```

The code is in `src/prophelper`: `store.py` (SQLite, schema and migrations), the pure modules `stages.py`,
`scoring.py`, `money.py`, `commute.py`, `redflags.py` and `parsers.py`, `enrich.py` (puts them together for the
pages), and the pages in `routes_*.py` with templates in `templates/`. The product and architecture decisions are
in [docs/DESIGN.md](docs/DESIGN.md). Packaging (PyInstaller) is in `packaging/`.
