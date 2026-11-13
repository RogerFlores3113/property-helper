"""Sharing with other people: a comparison as one safe web page, and a search as a file a housemate can read back in.
No web framework code here (the routes are in ``routes_compare.py`` and ``routes_data.py``).

Two things go out of the app, and both leave things OUT on purpose:

* ``comparison_html``: one self-contained page (styles inline, no scripts, no outside links, no pictures, no map).
  Contacts, phone numbers, emails, AI notes and documents are never in it. The person's own notes only when they ask.
* ``export_search`` / ``read_export``: a JSON file with the search, what matters, the important places it uses and the
  places with their facts and listing text. No contacts, documents, notes, ratings, AI text, stage or AI key.

Everything that comes IN from a file is treated as untrusted text: size capped, shape checked, only known keys read,
every value cleaned again by the same rules as a form (see ``Store``).
"""
from __future__ import annotations

import json
import re
import secrets
import time
from datetime import date
from typing import Any

from . import compare, helpers
from .store import (COMMUTE_MODES, PLACE_INT, PLACE_REAL, PLACE_TEXT, Store, people_slots)

FORMAT_NAME = "property-helper-search"
FORMAT_VERSION = 1
MAX_IMPORT_BYTES = 5 * 1024 * 1024
MAX_PLACES, MAX_CRITERIA, MAX_ANCHORS = 500, 60, 60

# What a shared file never carries: what the person wrote, what an AI wrote, and where they are in their search.
LEFT_OUT_PLACE_FIELDS = {"notes", "ai_notes", "fit_notes", "red_flags", "rating", "fit_score"}
SHARED_TEXT = tuple(f for f in PLACE_TEXT if f not in LEFT_OUT_PLACE_FIELDS)
SHARED_REAL = PLACE_REAL
SHARED_INT = tuple(f for f in PLACE_INT if f not in LEFT_OUT_PLACE_FIELDS)

# Rows of Compare that are about the person, not the place.
_PERSONAL_ROWS = {"stage", "rating", "opinions"}


# --------------------------------------------------------------------------- the page to share
_URL_START = re.compile(r"(https?):(?=//)", re.IGNORECASE)


def defang(html: str) -> str:
    """Break 'http://' and 'https://' in the text of the page (a zero-width space after the colon) so the file holds no
    web address a browser or a person could follow by accident. The text still reads the same."""
    return _URL_START.sub(r"\1:&#8203;", html)


def _text_cell(text: str) -> dict[str, Any]:
    return compare._cell(text or None)


def comparison_sections(places: list[dict[str, Any]], include_notes: bool = False) -> list[dict[str, Any]]:
    """Compare's sections for these enriched places, without the personal rows, plus cash at move-in and the
    possible-scam marks. With ``include_notes`` the person's own notes and their people's ratings are added."""
    sections = []
    for sec in compare.build_rows(places):
        rows = [r for r in sec["rows"] if include_notes or r["key"] not in _PERSONAL_ROWS]
        if rows:
            sections.append({"title": sec["title"], "rows": rows})
    cash = [p["cost"].get("cash_at_move_in") for p in places]
    if any(cash):
        cells = [compare._money(c["total"]) if c else compare._cell(None) for c in cash]
        row = compare._row("cash_at_move_in", "Cash needed on move-in day", cells, "low", only_if_any=True)
        if row:
            target = next((s for s in sections if s["title"] == "Dates and money up front"), None)
            if target is None:
                sections.append({"title": "Dates and money up front", "rows": [row]})
            else:
                target["rows"].append(row)
    scam_cells = []
    for p in places:
        flags = list(p.get("flags") or [])
        if p.get("possible_scam"):
            scam_cells.append(_text_cell("Check first: possible scam. " + (" ".join(flags[:3]) if flags else "")))
        elif flags:
            scam_cells.append(_text_cell(" ".join(flags[:3])))
        else:
            scam_cells.append(_text_cell("Nothing found"))
    sections.append({"title": "Possible scam signs", "rows": [compare._row("scam", "What to check", scam_cells)]})
    if include_notes:
        note_cells = [_text_cell((p.get("notes") or "").strip()[:2000]) for p in places]
        opinion_cells = []
        for p in places:
            lines = [f"{o['person']}: {o['rating'] if o['rating'] is not None else '-'}" + (f", {o['note']}" if o["note"] else "")
                     for o in p.get("opinion_rows") or []]
            opinion_cells.append(_text_cell("\n".join(lines)))
        rows = [compare._row("notes", "My notes", note_cells, only_if_any=True),
                compare._row("people", "What each person thinks", opinion_cells, only_if_any=True)]
        rows = [r for r in rows if r]
        if rows:
            sections.append({"title": "My notes", "rows": rows})
    return sections


def comparison_html(templates: Any, places: list[dict[str, Any]], include_notes: bool = False) -> str:
    """The shareable page as one string. ``templates`` is the app's Jinja environment holder (``app.state.templates``)."""
    sections = comparison_sections(places, include_notes)
    summary = compare.summary_lines(places, sections)
    html = templates.get_template("share.html").render(places=places, sections=sections, summary=summary,
                                                       include_notes=include_notes, made_on=helpers.day_text(helpers.today(), True))
    return defang(html)


def comparison_filename() -> str:
    return f"property-helper-comparison-{date.today().isoformat()}.html"


# --------------------------------------------------------------------------- export a search
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")[:40] or "search"


def export_filename(search: dict[str, Any]) -> str:
    return f"property-helper-search-{_slug(search['name'])}-{date.today().isoformat()}.json"


def export_search(store: Store, search_id: int) -> dict[str, Any]:
    """The search as a plain dict, ready for ``json.dumps``. See the module text for what is left out."""
    search = store.get_search(search_id)
    criteria = store.list_criteria(search_id)
    places = store.list_places(search_id)
    commutes = store.list_commutes_for_search(search_id)
    anchors_by_id = {a["id"]: a for a in store.list_anchors()}
    used: list[int] = []

    def anchor_index(anchor_id: Any) -> int | None:
        try:
            aid = int(anchor_id)
        except (TypeError, ValueError):
            return None
        if aid not in anchors_by_id:
            return None
        if aid not in used:
            used.append(aid)
        return used.index(aid)

    crit_out = []
    for c in criteria:
        target = dict(c["target"])
        if c["kind"] == "commute":
            idx = anchor_index(target.pop("anchor_id", None))
            if idx is not None:
                target["anchor"] = idx
        crit_out.append({"kind": c["kind"], "label": c["label"], "weight": c["weight"], "dealbreaker": bool(c["dealbreaker"]),
                         "target": target})
    places_out = []
    for p in places:
        item: dict[str, Any] = {}
        for key in (*SHARED_TEXT, *SHARED_REAL, *SHARED_INT):
            if p.get(key) not in (None, ""):
                item[key] = p[key]
        if p.get("photo_urls"):
            item["photo_urls"] = list(p["photo_urls"])
        if p.get("dishwasher") is not None:
            item["dishwasher"] = bool(p["dishwasher"])
        cm = []
        for c in commutes.get(p["id"], []):
            idx = anchor_index(c["anchor_id"])
            if idx is not None:
                cm.append({"anchor": idx, "mode": c["mode"], "minutes": c["minutes"]})
        if cm:
            item["commutes"] = cm
        places_out.append(item)
    anchors_out = [{k: anchors_by_id[a][k] for k in ("name", "address", "lat", "lng")} for a in used]
    return {
        "format": FORMAT_NAME, "version": FORMAT_VERSION, "exported_on": date.today().isoformat(),
        "search": {"name": search["name"], "mode": search["mode"], "area": search["area"], "move_in": search["move_in"],
                   "target_close": search["target_close"], "budget_max": search["budget_max"],
                   "hide_dealbreakers": bool(search["hide_dealbreakers"]), "people": search["people"],
                   "people_names": list(search.get("people_names") or [])},
        "criteria": crit_out, "anchors": anchors_out, "places": places_out,
    }


def export_bytes(store: Store, search_id: int) -> bytes:
    return json.dumps(export_search(store, search_id), indent=1, ensure_ascii=False).encode("utf-8")


# --------------------------------------------------------------------------- read one back
class NotAnExport(ValueError):
    """Plain words for why a file can't be read as a shared search."""


def read_export(data: bytes) -> dict[str, Any]:
    """Check an uploaded file and return it as a dict with the same shape ``export_search`` makes. Nothing is written.
    Raises ``NotAnExport`` (plain words) for a file that is too big, not JSON, not from this app or too large inside."""
    if len(data) > MAX_IMPORT_BYTES:
        raise NotAnExport("That file is too big (limit 5 MB). A shared search is usually much smaller.")
    try:
        doc = json.loads(data.decode("utf-8-sig"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise NotAnExport("That isn't a shared search. Choose a file made by Export this search.") from None
    if not isinstance(doc, dict) or doc.get("format") != FORMAT_NAME:
        raise NotAnExport("That isn't a shared search from Property Helper. Choose a file made by Export this search.")
    version = doc.get("version")
    if not isinstance(version, int) or isinstance(version, bool) or version != FORMAT_VERSION:
        raise NotAnExport("That file was made by a different version of Property Helper, so it can't be read here.")
    search, crits, anchors, places = doc.get("search"), doc.get("criteria", []), doc.get("anchors", []), doc.get("places", [])
    if not isinstance(search, dict) or not all(isinstance(x, list) for x in (crits, anchors, places)):
        raise NotAnExport("That shared search file is damaged, so nothing was added.")
    if len(places) > MAX_PLACES or len(crits) > MAX_CRITERIA or len(anchors) > MAX_ANCHORS:
        raise NotAnExport(f"That file holds more than a search should (over {MAX_PLACES} places), so nothing was added.")
    if not str(search.get("name") or "").strip():
        raise NotAnExport("That shared search has no name, so nothing was added.")
    if not all(isinstance(x, dict) for x in (*crits, *anchors, *places)):
        raise NotAnExport("That shared search file is damaged, so nothing was added.")
    return doc


def preview_text(doc: dict[str, Any]) -> str:
    """'Adds a search named X with 7 places' (the name is cut to a sane length; the page escapes it)."""
    name = " ".join(str(doc["search"].get("name") or "").split())[:200]
    n = len(doc["places"])
    return f"Adds a search named {name} with {n} place{'s' if n != 1 else ''}"


def apply_import(store: Store, doc: dict[str, Any]) -> dict[str, Any]:
    """Make a NEW search from a checked export. All or nothing for the search itself; a place or a criterion that
    can't be read is skipped and counted. Important places that match one you already have (same name and address)
    are reused. Returns ``{"search", "places", "skipped", "link_dropped"}``."""
    s = doc["search"]
    skipped = dropped = 0
    created = 0
    with store._write():
        mode = str(s.get("mode") or "rent")
        fields = {k: s.get(k) for k in ("area", "move_in", "target_close", "budget_max", "people", "people_names") if s.get(k) not in (None, "")}
        fields["hide_dealbreakers"] = bool(s.get("hide_dealbreakers"))
        search = store.add_search(str(s.get("name") or ""), mode, **fields)
        sid = search["id"]
        existing = store.list_anchors()
        anchor_ids: dict[int, int] = {}
        for i, a in enumerate(doc["anchors"]):
            name = " ".join(str(a.get("name") or "").split())
            if not name:
                continue
            addr = str(a.get("address") or "").strip()
            match = next((e for e in existing if e["name"].lower() == name.lower() and (e["address"] or "").lower() == addr.lower()), None)
            try:
                made = match or store.add_anchor(name, addr, a.get("lat"), a.get("lng"))
            except ValueError:
                skipped += 1
                continue
            if match is None:
                existing.append(made)
            anchor_ids[i] = made["id"]
        for c in doc["criteria"]:
            target = c.get("target") if isinstance(c.get("target"), dict) else {}
            target = dict(target)
            idx = target.pop("anchor", None)
            if idx is not None:
                if isinstance(idx, int) and not isinstance(idx, bool) and idx in anchor_ids:
                    target["anchor_id"] = anchor_ids[idx]
            try:
                store.add_criterion(sid, str(c.get("kind") or ""), label=str(c.get("label") or ""), weight=c.get("weight", 10),
                                    dealbreaker=c.get("dealbreaker"), target=target)
            except (ValueError, TypeError):
                skipped += 1
        for item in doc["places"]:
            fields = {k: item[k] for k in (*SHARED_TEXT, *SHARED_REAL, *SHARED_INT, "photo_urls", "dishwasher") if k in item}
            if fields.get("url") and store.find_duplicate(url=str(fields["url"])) is not None:
                fields.pop("url")  # a link is saved once across all searches; this one is already in use
                dropped += 1
            try:
                place, made_new = store.add_place(search_id=sid, by="you", **fields)
            except (ValueError, TypeError):
                skipped += 1
                continue
            if not made_new:
                skipped += 1
                continue
            created += 1
            for cm in item.get("commutes") or []:
                try:
                    idx = cm.get("anchor")
                    if isinstance(idx, int) and not isinstance(idx, bool) and idx in anchor_ids and str(cm.get("mode")) in COMMUTE_MODES:
                        store.set_commute(place["id"], anchor_ids[idx], str(cm["mode"]), cm.get("minutes"), "you")
                except (ValueError, TypeError, AttributeError):
                    skipped += 1
    return {"search": store.get_search(sid), "places": created, "skipped": skipped, "link_dropped": dropped}


# --------------------------------------------------------------------------- a file waiting for "Add it"
_PENDING: dict[str, tuple[float, str, dict[str, Any]]] = {}
PENDING_SECONDS = 30 * 60
PENDING_MAX = 5


def hold(filename: str, doc: dict[str, Any]) -> str:
    """Keep a checked file in memory (never on disk) while the person looks at the preview. Returns its token."""
    now = time.monotonic()
    for t in [t for t, (at, _n, _d) in _PENDING.items() if now - at > PENDING_SECONDS]:
        del _PENDING[t]
    while len(_PENDING) >= PENDING_MAX:
        del _PENDING[min(_PENDING, key=lambda t: _PENDING[t][0])]
    token = secrets.token_urlsafe(16)
    _PENDING[token] = (now, filename, doc)
    return token


def held(token: str) -> tuple[str, dict[str, Any]] | None:
    got = _PENDING.get(token or "")
    if got is None or time.monotonic() - got[0] > PENDING_SECONDS:
        _PENDING.pop(token or "", None)
        return None
    return got[1], got[2]


def release(token: str) -> None:
    _PENDING.pop(token or "", None)


def opinions_for(store: Store, place_id: int) -> list[dict[str, Any]]:
    """The people's saved opinions of a place (for the 'include my notes' option)."""
    try:
        return store.list_opinions(place_id)
    except Exception:
        return []


__all__ = ["people_slots", "comparison_html", "export_bytes", "read_export", "apply_import"]
