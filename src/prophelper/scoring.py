"""Weighted scoring of a place against a search's criteria (DESIGN section 3). Pure: no database, no web.

``score_place`` returns, for one place:

* ``items``: one dict per criterion with ``score`` (0 to 1), ``known`` (False when the place has no value, which
  scores 0.5), ``dealbreaker_status`` (``""`` when the criterion is not a deal-breaker, else ``"pass"``, ``"fail"`` or
  ``"check"``), the place's ``value`` and the wanted ``target`` as plain words, and a short ``detail`` line.
* ``total``: 0 to 100, ``100 * sum(weight * score) / sum(weight)`` rounded, or None when there is nothing to score.
* ``unknown``, ``failed`` and ``check``: labels, so a page can say what to fill in.
* ``fails_dealbreaker`` / ``needs_check``: booleans for hiding and for the "check this" note.
"""
from __future__ import annotations

from typing import Any, Iterable

from . import commute as commute_mod
from . import money

KINDS: tuple[str, ...] = ("price", "beds", "baths", "sqft", "commute", "laundry", "dishwasher", "parking", "pets",
                          "newer", "custom")
KIND_LABELS: dict[str, str] = {
    "price": "Monthly cost", "beds": "Bedrooms", "baths": "Bathrooms", "sqft": "Size", "commute": "Commute",
    "laundry": "Laundry", "dishwasher": "Dishwasher", "parking": "Parking", "pets": "Pets", "newer": "Newer building",
    "custom": "Your own score",
}
UNKNOWN_SCORE = 0.5
LAUNDRY_RANK = {"in_unit": 2, "in_building": 1, "none": 0}
LAUNDRY_WORDS = {"in_unit": "in the unit", "in_building": "in the building", "none": "none"}
PARKING_RANK = {"garage": 3, "covered": 2, "lot": 1, "street": 0, "none": -1}
PETS_OK = {"cats": ("cats", "both"), "dogs": ("dogs", "both"), "both": ("both",)}


def _num(v: Any) -> float | None:
    return money.num(v)


def _fmt(n: float | None, prefix: str = "", suffix: str = "") -> str:
    if n is None:
        return ""
    if prefix == "$" or abs(n - round(n)) < 1e-9:
        return f"{prefix}{n:,.0f}{suffix}"
    return f"{prefix}{n:,.1f}{suffix}"


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def default_label(kind: str, target: dict[str, Any] | None = None) -> str:
    """A plain label for a criterion made without one: 'Monthly cost, at most $1,600'."""
    t = target or {}
    if kind == "price":
        return f"Monthly cost, at most {_fmt(_num(t.get('max')), '$')}" if _num(t.get("max")) else KIND_LABELS[kind]
    if kind in ("beds", "baths"):
        return f"{KIND_LABELS[kind]}, at least {_fmt(_num(t.get('min')))}" if _num(t.get("min")) is not None else KIND_LABELS[kind]
    if kind == "sqft":
        return f"Size, at least {_fmt(_num(t.get('min')), '', ' sq ft')}" if _num(t.get("min")) else KIND_LABELS[kind]
    if kind == "commute":
        mins, mode = _num(t.get("minutes")), t.get("mode") or "bike"
        return f"Commute by {mode}, {_fmt(mins, '', ' min')} or less" if mins else "Commute"
    if kind == "laundry":
        return "Washer and dryer in the unit" if (t.get("want") or "in_unit") == "in_unit" else "Laundry in the building"
    if kind == "newer":
        return f"Built {t['year']} or later" if t.get("year") else KIND_LABELS[kind]
    return KIND_LABELS.get(kind, kind.title())


def _auto_label(kind: str, target: dict[str, Any], ctx: dict[str, Any]) -> str:
    """The label for a criterion saved without one. A commute names its important place, so two never read the same."""
    if kind == "commute":
        anchors = ctx.get("anchors", {})
        a = anchors.get(target.get("anchor_id")) if target.get("anchor_id") is not None else next(iter(anchors.values()), None)
        if a:
            return commute_mod.commute_label(target.get("mode") or "bike", _num(target.get("minutes")), a["name"])
    return default_label(kind, target)


def _result(score: float | None, value: str, target: str, detail: str, *, known: bool, passes: bool | None) -> dict[str, Any]:
    return {"score": UNKNOWN_SCORE if score is None else _clamp(score), "known": known, "value": value, "target": target,
            "detail": detail, "passes": passes}


def _unknown(target: str, what: str) -> dict[str, Any]:
    return _result(None, "", target, f"{what} is not filled in, so it counts as a maybe.", known=False, passes=None)


def _score_price(c: dict[str, Any], place: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    t = c["target"]
    limit = _num(t.get("max")) or _num(ctx.get("budget_max"))
    cost = ctx.get("cost") or {}
    total = cost.get("total")
    target = f"at most {_fmt(limit, '$')} a month" if limit else "no limit set"
    if total is None:
        return _unknown(target, "The monthly cost")
    value = f"{_fmt(total, '$')} a month"
    if not limit:
        return _result(1.0, value, target, "No price limit set on this search.", known=True, passes=True)
    if total <= limit:
        return _result(1.0, value, target, f"{_fmt(limit - total, '$')} under your limit.", known=True, passes=True)
    score = 1 - (total - limit) / (0.25 * limit)
    return _result(score, value, target, f"{_fmt(total - limit, '$')} over your limit.", known=True, passes=False)


def _score_min(c: dict[str, Any], place: dict[str, Any], field: str, label: str, unit: str) -> dict[str, Any]:
    want = _num(c["target"].get("min"))
    target = f"at least {_fmt(want, '', unit)}" if want is not None else "any"
    have = _num(place.get(field))
    if have is None:
        return _unknown(target, label)
    value = _fmt(have, '', unit)
    if want is None or have >= want:
        return _result(1.0, value, target, "Meets it.", known=True, passes=True)
    if field == "sqft":
        score = (have - 0.6 * want) / (0.4 * want) if want > 0 else 0.0
    else:
        score = 0.5 if have >= want - 1 else 0.0
    return _result(score, value, target, "Below what you wanted.", known=True, passes=False)


def _score_commute(c: dict[str, Any], place: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    t = c["target"]
    mins = _num(t.get("minutes"))
    mode = t.get("mode") or "bike"
    anchors = ctx.get("anchors", {})
    # A commute with no place chosen means the first important place (the form's "First one" choice).
    anchor = anchors.get(t["anchor_id"]) if t.get("anchor_id") is not None else next(iter(anchors.values()), None)
    anchor_name = anchor["name"] if anchor else "that place"
    target = f"{_fmt(mins, '', ' min')} or less by {mode} to {anchor_name}" if mins else "any"
    if anchor is None:
        gone = t.get("anchor_id") is not None
        return _result(None, "", target, "The important place you wanted to reach was removed, so choose another one in What matters." if gone
                       else "There is no important place yet. Add one on the Search page, like Work or Campus.", known=False, passes=None)
    found = commute_mod.resolve(place, anchor, mode, ctx.get("commutes", ()))
    if found is None:
        if not commute_mod.has_point(anchor):
            return _result(None, "", target, commute_mod.NO_LOCATION_MESSAGE.format(name=anchor_name), known=False, passes=None)
        return _unknown(target, f"The {mode} time to {anchor_name}")
    value = found["label"]
    if not mins:
        return _result(1.0, value, target, "", known=True, passes=True)
    have = found["minutes"]
    score = 1.0 if have <= mins else 1 - (have - mins) / mins
    detail = "Within your limit." if have <= mins else f"{have - mins:.0f} min over your limit."
    if found["source"] == "estimate":
        detail += " This is an estimate from the map, so check it."
    return _result(score, value, target, detail, known=True, passes=have <= mins)


def _score_laundry(c: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    want = c["target"].get("want") or "in_unit"
    target = LAUNDRY_WORDS.get(want, "in the unit")
    have = str(place.get("laundry") or "")
    if have not in LAUNDRY_RANK:
        return _unknown(target, "Laundry")
    if want == "in_unit":
        score = {"in_unit": 1.0, "in_building": 0.5, "none": 0.0}[have]
    else:
        score = {"in_unit": 1.0, "in_building": 1.0, "none": 0.0}[have]
    return _result(score, LAUNDRY_WORDS[have], target, "", known=True, passes=score >= 1.0)


def _score_yes(value_known: bool, yes: bool, target: str, value: str, what: str) -> dict[str, Any]:
    if not value_known:
        return _unknown(target, what)
    return _result(1.0 if yes else 0.0, value, target, "", known=True, passes=yes)


def _score_dishwasher(c: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    d = place.get("dishwasher")
    return _score_yes(d is not None, bool(d), "has one", "yes" if d else "no", "Dishwasher")


def _score_parking(c: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    want = c["target"].get("want") or "lot"
    have = str(place.get("parking") or "")
    target = "off-street parking" if want == "lot" else f"{want} parking"
    if have not in PARKING_RANK:
        return _unknown(target, "Parking")
    ok = PARKING_RANK[have] >= PARKING_RANK.get(want, 1)
    return _score_yes(True, ok, target, have, "Parking")


def _score_pets(c: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    want = c["target"].get("want") or ""
    have = str(place.get("pets") or "")
    target = f"{want} allowed" if want else "pets allowed"
    if have not in ("cats", "dogs", "both", "none"):
        return _unknown(target, "The pet policy")
    ok = have in PETS_OK.get(want, ("cats", "dogs", "both"))
    return _score_yes(True, ok, target, have if have != "none" else "no pets", "The pet policy")


def _score_newer(c: dict[str, Any], place: dict[str, Any]) -> dict[str, Any]:
    year = _num(c["target"].get("year")) or 2000
    have = _num(place.get("year_built"))
    target = f"built {_fmt(year)} or later"
    if have is None:
        return _unknown(target, "The year built")
    return _score_yes(True, have >= year, target, f"built {_fmt(have)}", "The year built")


def _score_custom(c: dict[str, Any], place: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    given = (ctx.get("custom_scores") or {}).get(c.get("id"))
    target = "your own score, 0 to 5"
    if given is None:
        return _unknown(target, "Your score")
    return _result(_num(given) / 5.0, f"{_fmt(_num(given))} of 5", target, "", known=True, passes=_num(given) > 0)


def score_criterion(c: dict[str, Any], place: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """One criterion against one place. ``ctx``: cost, budget_max, anchors ({id: anchor}), commutes, custom_scores."""
    kind = c["kind"]
    if kind == "price":
        r = _score_price(c, place, ctx)
    elif kind == "beds":
        r = _score_min(c, place, "beds", "Bedrooms", " bed")
    elif kind == "baths":
        r = _score_min(c, place, "baths", "Bathrooms", " bath")
    elif kind == "sqft":
        r = _score_min(c, place, "sqft", "The size", " sq ft")
    elif kind == "commute":
        r = _score_commute(c, place, ctx)
    elif kind == "laundry":
        r = _score_laundry(c, place)
    elif kind == "dishwasher":
        r = _score_dishwasher(c, place)
    elif kind == "parking":
        r = _score_parking(c, place)
    elif kind == "pets":
        r = _score_pets(c, place)
    elif kind == "newer":
        r = _score_newer(c, place)
    elif kind == "custom":
        r = _score_custom(c, place, ctx)
    else:
        r = _unknown("", kind)
    if not c.get("dealbreaker"):
        status = ""
    elif r["passes"] is None:
        status = "check"
    else:
        status = "pass" if r["passes"] else "fail"
    return {"id": c.get("id"), "kind": kind, "label": c.get("label") or _auto_label(kind, c["target"], ctx),
            "weight": c.get("weight", 0), "dealbreaker": bool(c.get("dealbreaker")), "dealbreaker_status": status, **r}


def score_place(place: dict[str, Any], criteria: Iterable[dict[str, Any]], *, mode: str = "rent",
                anchors: Iterable[dict[str, Any]] = (), commutes: Iterable[dict[str, Any]] = (),
                custom_scores: dict[int, float] | None = None, budget_max: float | None = None,
                settings: dict[str, Any] | None = None, cost: dict[str, Any] | None = None) -> dict[str, Any]:
    """Score a place. ``criteria`` rows have ``kind``, ``weight``, ``dealbreaker`` and ``target`` (a dict).
    ``commutes`` are the place's stored commute rows; ``cost`` can be passed to avoid computing it twice."""
    ctx = {"cost": cost if cost is not None else money.true_monthly_cost(place, mode, settings),
           "budget_max": budget_max, "anchors": {a["id"]: a for a in anchors}, "commutes": list(commutes),
           "custom_scores": custom_scores or {}}
    items = [score_criterion(c, place, ctx) for c in criteria]
    total_w = sum(max(0.0, float(i["weight"] or 0)) for i in items)
    total = None
    if items and total_w > 0:
        total = int(round(100 * sum(max(0.0, float(i["weight"] or 0)) * i["score"] for i in items) / total_w + 1e-9))
    failed = [i["label"] for i in items if i["dealbreaker_status"] == "fail"]
    check = [i["label"] for i in items if i["dealbreaker_status"] == "check"]
    return {"total": total, "items": items, "unknown": [i["label"] for i in items if not i["known"]],
            "failed": failed, "check": check, "fails_dealbreaker": bool(failed), "needs_check": bool(check),
            "cost": ctx["cost"]}


def score_band(total: int | None) -> str:
    """'good' (70 and up), 'ok' (40 to 69), 'low' (under 40) or '' when there is no score."""
    if total is None:
        return ""
    return "good" if total >= 70 else "ok" if total >= 40 else "low"
