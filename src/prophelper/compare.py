"""Compare two to four places side by side. Pure: it takes enriched places (see ``enrich.py``) and returns rows.

``build_rows(places)`` returns a list of sections; each section is ``{"title", "rows"}`` and each row is
``{"key", "label", "cells", "differs", "best_note"}``. A cell is ``{"text", "value", "best", "unknown"}``:

* ``text``: what the page shows.
* ``value``: the number used to compare (None when unknown or not a number).
* ``best``: True on the best value in the row (lowest cost, highest score and so on). A row where every known value
  is the same, or where fewer than two places have a value, marks no best.
* ``differs``: True when the known values are not all the same, so the page can highlight the row.

Which way is better is set per row in ``ROW_BETTER``: ``low`` (cost, fees, commute minutes), ``high`` (score, size,
newer) or ``None`` (a fact where neither is better, such as bedrooms: only differences are shown).
"""
from __future__ import annotations

from typing import Any

from . import helpers

MIN_PLACES, MAX_PLACES = 2, 4
LAUNDRY_RANK = {"in_unit": 2, "in_building": 1, "none": 0}
LAUNDRY_TEXT = {"in_unit": "In the unit", "in_building": "In the building", "none": "None"}
PARKING_RANK = {"garage": 4, "covered": 3, "lot": 2, "street": 1, "none": 0}
PARKING_TEXT = {"garage": "Garage", "covered": "Covered", "lot": "Lot", "street": "Street", "none": "None"}
PETS_TEXT = {"cats": "Cats", "dogs": "Dogs", "both": "Cats and dogs", "none": "No pets"}
UNKNOWN = "unknown"


class CompareError(ValueError):
    """A plain-words reason the comparison can't be made (too few or too many places)."""


def parse_ids(values: Any) -> list[int]:
    """Ids from '1,2,3', from a list of such strings, or from a mix; repeats dropped, order kept.
    Raises CompareError for anything that is not a whole number."""
    parts: list[str] = []
    for v in (values if isinstance(values, (list, tuple)) else [values]):
        parts.extend(str(v or "").replace(" ", ",").split(","))
    out: list[int] = []
    for p in parts:
        if not p:
            continue
        if not p.isdigit():
            raise CompareError("Those aren't place numbers. Pick the places with the boxes below.")
        n = int(p)
        if n > 0 and n not in out:
            out.append(n)
    return out


def check_count(n: int) -> None:
    if n < MIN_PLACES:
        raise CompareError(f"Pick at least {MIN_PLACES} places to compare. You picked {n}.")
    if n > MAX_PLACES:
        raise CompareError(f"Compare takes {MIN_PLACES} to {MAX_PLACES} places at a time. You picked {n}, so take {n - MAX_PLACES} off.")


def mark(cells: list[dict[str, Any]], better: str | None) -> tuple[bool, str]:
    """Set ``best`` on the cells of one row, in place. Returns (differs, plain note about the best)."""
    known = [c["value"] for c in cells if c["value"] is not None]
    differs = len(set(round(v, 4) for v in known)) > 1
    for c in cells:
        c["best"] = False
    if not differs or better not in ("low", "high"):
        return differs, ""
    target = min(known) if better == "low" else max(known)
    for c in cells:
        c["best"] = c["value"] is not None and abs(c["value"] - target) < 1e-9
    return differs, "lowest" if better == "low" else "highest"


def _cell(text: Any, value: float | None = None) -> dict[str, Any]:
    unknown = text is None or text == ""
    return {"text": UNKNOWN if unknown else str(text), "value": value, "best": False, "unknown": unknown}


def _money(v: Any, cents: bool = False) -> dict[str, Any]:
    return _cell(helpers.money(v, cents=cents) if v is not None else None, float(v) if v is not None else None)


def _num(v: Any, suffix: str = "") -> dict[str, Any]:
    return _cell(helpers.number_text(v) + suffix if v not in (None, "") else None, float(v) if v not in (None, "") else None)


def _yes_no(v: Any) -> dict[str, Any]:
    if v is None:
        return _cell(None)
    return _cell("Yes" if v else "No", 1.0 if v else 0.0)


def _plain(text: Any) -> dict[str, Any]:
    return _cell(text or None)


def _row(key: str, label: str, cells: list[dict[str, Any]], better: str | None = None, *, only_if_any: bool = False) -> dict[str, Any] | None:
    if only_if_any and all(c["unknown"] for c in cells):
        return None
    differs, note = mark(cells, better)
    return {"key": key, "label": label, "cells": cells, "differs": differs, "best_note": note}


def _commute_key(c: dict[str, Any]) -> tuple[str, str]:
    return (c.get("anchor", ""), c.get("mode", ""))


def build_rows(places: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sections of rows for these enriched places (same order as ``places``)."""
    sections: list[dict[str, Any]] = []

    def section(title: str, rows: list[dict[str, Any] | None]) -> None:
        rows = [r for r in rows if r]
        if rows:
            sections.append({"title": title, "rows": rows})

    # ---- the headline numbers
    section("The short version", [
        _row("cost", "True monthly cost", [_money(p["cost_total"], True) for p in places], "low"),
        _row("score", "Fit score (out of 100)", [_num(p["score_total"]) for p in places], "high"),
        _row("stage", "Stage", [_plain(p["stage"]) for p in places]),
        _row("rating", "Your rating (1 to 5)", [_num(p.get("rating")) for p in places], "high", only_if_any=True),
    ])

    # ---- cost line by line
    line_keys: list[tuple[str, str]] = []
    for p in places:
        for line in p["cost"]["lines"]:
            if not any(k == line["key"] for k, _ in line_keys):
                line_keys.append((line["key"], line["label"]))
    cost_rows = []
    for key, label in line_keys:
        cells = []
        for p in places:
            found = next((ln for ln in p["cost"]["lines"] if ln["key"] == key), None)
            amount = found["amount"] if found else None
            cells.append(_money(amount, True) if amount is not None else _cell(None))
        cost_rows.append(_row("cost-" + key, label, cells, "low", only_if_any=True))
    cost_rows.append(_row("missing", "Not counted yet", [_plain(", ".join(p["cost"]["missing"]) or "nothing missing") for p in places]))
    section("What it really costs, line by line", cost_rows)

    # ---- the facts
    section("The place", [
        _row("price", "Listed price", [_money(p.get("price")) for p in places], "low"),
        _row("beds", "Bedrooms", [_num(p.get("beds")) for p in places]),
        _row("baths", "Bathrooms", [_num(p.get("baths")) for p in places]),
        _row("sqft", "Size (sq ft)", [_num(p.get("sqft")) for p in places], "high"),
        _row("year_built", "Year built", [_num(p.get("year_built")) for p in places], "high"),
        _row("laundry", "Laundry", [_cell(LAUNDRY_TEXT.get(p.get("laundry") or ""), LAUNDRY_RANK.get(p.get("laundry") or "")) for p in places], "high"),
        _row("dishwasher", "Dishwasher", [_yes_no(p.get("dishwasher")) for p in places], "high"),
        _row("parking", "Parking", [_cell(PARKING_TEXT.get(p.get("parking") or ""), PARKING_RANK.get(p.get("parking") or "")) for p in places], "high"),
        _row("pets", "Pets", [_cell(PETS_TEXT.get(p.get("pets") or "")) for p in places]),
        _row("utilities", "Utilities included", [_plain(p.get("utilities_included")) for p in places], only_if_any=True),
    ])
    section("Dates and money up front", [
        _row("available", "Available from", [_plain(helpers.day_text(p["available_from"]) if p.get("available_from") else "") for p in places], only_if_any=True),
        _row("lease_months", "Lease length (months)", [_num(p.get("lease_months")) for p in places], only_if_any=True),
        _row("deposit", "Deposit (comes back)", [_money(p.get("deposit")) for p in places], "low", only_if_any=True),
        _row("upfront", "Fees paid once (application, move-in, broker, pet)", [_money(p["cost"].get("one_time_total")) if p["cost"].get("mode") == "rent" else _cell(None) for p in places], "low", only_if_any=True),
    ])

    # ---- commutes
    seen: list[tuple[str, str]] = []
    for p in places:
        for c in p["commutes"]:
            if _commute_key(c) not in seen:
                seen.append(_commute_key(c))
    commute_rows = []
    for anchor, mode in seen:
        cells = []
        for p in places:
            c = next((x for x in p["commutes"] if _commute_key(x) == (anchor, mode)), None)
            cells.append(_cell(c["label"], float(c["minutes"])) if c else _cell(None))
        commute_rows.append(_row(f"commute-{anchor}-{mode}", f"{mode.capitalize()} to {anchor}", cells, "low"))
    section("Commutes", commute_rows)

    # ---- the score, criterion by criterion
    labels: list[str] = []
    for p in places:
        for item in p["score"]["items"]:
            if item["label"] not in labels:
                labels.append(item["label"])
    score_rows = []
    for label in labels:
        cells = []
        for p in places:
            item = next((i for i in p["score"]["items"] if i["label"] == label), None)
            if item is None:
                cells.append(_cell(None))
            elif not item["known"] or item["score"] is None:
                cells.append(_cell(None))
            else:
                pct = round(item["score"] * 100)
                cells.append(_cell(f"{pct}%" + (" (fails)" if item.get("dealbreaker_status") == "fail" else ""), float(pct)))
        score_rows.append(_row("score-" + label, label, cells, "high"))
    section("Score, criterion by criterion", score_rows)
    return sections


def summary_lines(places: list[dict[str, Any]], sections: list[dict[str, Any]]) -> list[str]:
    """A few plain sentences: who is cheapest and who scores highest."""
    out: list[str] = []
    for key, what in (("cost", "lowest true monthly cost"), ("score", "highest fit score")):
        for sec in sections:
            for row in sec["rows"]:
                if row["key"] == key and row["differs"]:
                    winners = [p["title"] for p, c in zip(places, row["cells"]) if c["best"]]
                    if winners:
                        out.append(f"{' and '.join(winners)} has the {what}.")
    return out
