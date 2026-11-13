"""Commute estimates from two map points. Pure: no database, no web.

An estimate is straight-line miles times 1.3 (roads are not straight), then a speed per mode:
walk 3 mph, bike 10 mph, transit 12 mph plus 8 minutes, drive 25 mph plus 4 minutes.
A value the user or the AI typed always wins over an estimate.
"""
from __future__ import annotations

import math
from typing import Any, Iterable

MODES: tuple[str, ...] = ("walk", "bike", "transit", "drive")
MODE_LABELS = {"walk": "walk", "bike": "bike", "transit": "transit", "drive": "drive"}
ROAD_FACTOR = 1.3
SPEED_MPH = {"walk": 3.0, "bike": 10.0, "transit": 12.0, "drive": 25.0}
EXTRA_MINUTES = {"walk": 0, "bike": 0, "transit": 8, "drive": 4}
EARTH_RADIUS_MILES = 3958.8
SOURCES = ("estimate", "you", "ai")


def haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Straight-line distance between two points on Earth, in miles."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dlmb = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_MILES * math.asin(min(1.0, math.sqrt(a)))


def estimate_minutes(miles: float, mode: str) -> int:
    """Minutes for a straight-line distance by one mode (see the module note). At least 1."""
    if mode not in SPEED_MPH:
        raise ValueError(f"Unknown way to travel: {mode}. Use one of: {', '.join(MODES)}.")
    road = miles * ROAD_FACTOR
    return max(1, round(road / SPEED_MPH[mode] * 60 + EXTRA_MINUTES[mode]))


def label(minutes: int | float | None, source: str = "you", mode: str = "") -> str:
    """'about 12 min (estimate)' or '15 min (you)'."""
    if minutes is None:
        return ""
    n = int(round(minutes))
    way = f" {MODE_LABELS.get(mode, mode)}" if mode else ""
    if source == "estimate":
        return f"about {n} min{way} (estimate)"
    return f"{n} min{way}" + (f" ({source})" if source in ("you", "ai") else "")


def has_point(thing: dict[str, Any] | None) -> bool:
    try:
        return thing is not None and thing.get("lat") is not None and thing.get("lng") is not None \
            and -90 <= float(thing["lat"]) <= 90 and -180 <= float(thing["lng"]) <= 180
    except (TypeError, ValueError):
        return False


def miles_between(place: dict[str, Any] | None, anchor: dict[str, Any] | None) -> float | None:
    """Straight-line miles between a place and an anchor, or None when either has no location."""
    if not (has_point(place) and has_point(anchor)):
        return None
    return haversine_miles(float(place["lat"]), float(place["lng"]), float(anchor["lat"]), float(anchor["lng"]))


def estimate(place: dict[str, Any] | None, anchor: dict[str, Any] | None, mode: str) -> dict[str, Any] | None:
    """``{"minutes", "miles", "source": "estimate", "mode", "label"}`` or None when a location is missing."""
    miles = miles_between(place, anchor)
    if miles is None:
        return None
    minutes = estimate_minutes(miles, mode)
    return {"minutes": minutes, "miles": round(miles, 2), "source": "estimate", "mode": mode,
            "label": label(minutes, "estimate", mode)}


def resolve(place: dict[str, Any] | None, anchor: dict[str, Any] | None, mode: str,
            stored: Iterable[dict[str, Any]] = ()) -> dict[str, Any] | None:
    """The commute to show for one place, anchor and mode. A stored value from you or the AI wins; otherwise the
    estimate; otherwise None. ``stored`` is the rows of the commutes table (any of them: this picks the match)."""
    if anchor is None:
        return None
    for row in stored:
        if row.get("anchor_id") == anchor.get("id") and row.get("mode") == mode and row.get("source") in ("you", "ai") \
                and row.get("minutes") is not None:
            miles = miles_between(place, anchor)
            return {"minutes": row["minutes"], "miles": round(miles, 2) if miles is not None else None,
                    "source": row["source"], "mode": mode, "label": label(row["minutes"], row["source"], mode)}
    return estimate(place, anchor, mode)


def resolve_all(place: dict[str, Any], anchors: Iterable[dict[str, Any]], stored: Iterable[dict[str, Any]] = (),
                modes: Iterable[str] = MODES) -> list[dict[str, Any]]:
    """Every anchor by every mode that has an answer: ``[{"anchor", "anchor_id", "mode", ...resolve()}]``."""
    stored = list(stored)
    out = []
    for a in anchors:
        for m in modes:
            r = resolve(place, a, m, stored)
            if r:
                out.append({"anchor": a.get("name", ""), "anchor_id": a.get("id"), **r})
    return out


def top_commute(place: dict[str, Any], anchors: Iterable[dict[str, Any]], stored: Iterable[dict[str, Any]] = (),
                prefer_mode: str | None = None) -> dict[str, Any] | None:
    """The one commute a card shows: the first anchor's best answer. ``prefer_mode`` (a criterion's mode) first,
    else the fastest of walk, bike and drive."""
    anchors = list(anchors)
    stored = list(stored)
    for a in anchors:
        if prefer_mode:
            r = resolve(place, a, prefer_mode, stored)
            if r:
                return {"anchor": a.get("name", ""), "anchor_id": a.get("id"), **r}
        options = [r for m in ("walk", "bike", "drive") if (r := resolve(place, a, m, stored))]
        if options:
            best = min(options, key=lambda r: r["minutes"])
            return {"anchor": a.get("name", ""), "anchor_id": a.get("id"), **best}
    return None
