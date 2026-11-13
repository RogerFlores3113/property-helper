"""The calendar and tours.

    GET  /calendar                      month grid (?month=2027-07) of tours and place dates, with an agenda list under it
    GET  /calendar.ics                  the same dates as an iCalendar file (a download: only from inside the app)
    POST /places/{id}/tours             book a tour (date, time, length, with whom, where)
    POST /tours/{id}/status             mark a tour done, cancelled or booked again
    POST /tours/{id}/details            save the tour checklist, rating and notes
    POST /tours/{id}/delete             delete a tour (tick box to confirm)
"""
from __future__ import annotations

import calendar as _calendar
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from . import helpers, ics
from .deps import get_store, redirect, render
from .store import TOUR_ITEMS, NotFound, Store

router = APIRouter()

KIND_LABELS = {"tour": "Tour", "available": "Available", "lease_start": "Lease starts", "lease_end": "Lease ends"}
DATE_KEYS = (("available_from", "available"), ("lease_start", "lease_start"), ("lease_end", "lease_end"))
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def _month(value: str) -> date:
    """The first day of the month named by 'YYYY-MM' (this month for anything else)."""
    try:
        y, m = value.split("-")
        return date(int(y), int(m), 1)
    except (ValueError, AttributeError):
        return helpers.month_start(helpers.today())


def calendar_items(store: Store, search_id: int | None, start: date | None = None, end: date | None = None) -> list[dict[str, Any]]:
    """Everything with a date for one search, sorted by day then time. ``start`` (inclusive) and ``end`` (exclusive)
    cut it to a window; both None gives everything. Cancelled tours and places that were passed on are left out.
    Each item: ``date`` (a date), ``kind``, ``kind_label``, ``time`` ('' for all day), ``text``, ``title`` (the place),
    ``place_id``, ``href`` and, for a tour, ``tour`` (the stored row)."""
    if search_id is None:
        return []
    items: list[dict[str, Any]] = []
    for t in store.list_tours(search_id=search_id):
        if t["status"] == "cancelled":
            continue
        local = helpers.to_local(t["starts_at"])
        if local is None:
            continue
        items.append({"date": local.date(), "kind": "tour", "kind_label": KIND_LABELS["tour"], "time": helpers.clock_text(t["starts_at"]),
                      "sort": local.strftime("%H:%M"), "text": "Tour" + (" (done)" if t["status"] == "done" else ""),
                      "title": t["title"], "place_id": t["place_id"], "href": f"/places/{t['place_id']}#tours", "tour": t})
    for p in store.list_places(search_id):
        if p["stage"] == "Passed" or p["hidden"]:
            continue
        for key, kind in DATE_KEYS:
            try:
                d = date.fromisoformat(p[key]) if p.get(key) else None
            except ValueError:
                d = None
            if d:
                items.append({"date": d, "kind": kind, "kind_label": KIND_LABELS[kind], "time": "", "sort": "00:00",
                              "text": KIND_LABELS[kind], "title": p["title"], "place_id": p["id"], "href": f"/places/{p['id']}"})
    items = [i for i in items if (start is None or i["date"] >= start) and (end is None or i["date"] < end)]
    items.sort(key=lambda i: (i["date"], i["sort"], i["title"].lower()))
    return items


def ics_items(items: list[dict[str, Any]], places: dict[int, dict[str, Any]]) -> list[dict[str, Any]]:
    """The dicts :func:`ics.build_calendar` wants, from calendar items. A tour's notes, rating and checklist are never used."""
    out = []
    for it in items:
        place = places.get(it["place_id"], {})
        where = ", ".join(x for x in (place.get("address"), place.get("city")) if x)
        if it["kind"] == "tour":
            t = it["tour"]
            desc = "Tour" + (f" with {t['with_whom']}" if t["with_whom"] else "") + (f". {t['where_note']}" if t["where_note"] else "")
            out.append({"uid": f"tour-{t['id']}", "summary": f"Tour: {it['title']}", "description": desc, "location": where,
                        "starts_at": t["starts_at"], "duration_minutes": t["duration_minutes"], "updated": t.get("created_at")})
        else:
            out.append({"uid": f"place-{it['place_id']}-{it['kind']}", "summary": f"{it['text']}: {it['title']}", "location": where,
                        "date": it["date"].isoformat(), "updated": place.get("updated_at")})
    return out


def month_weeks(first: date, items: list[dict[str, Any]], today: date) -> list[list[dict[str, Any]]]:
    """The month as rows of seven cells, Monday first: ``{"date", "in_month", "today", "entries"}``."""
    by_day: dict[date, list[dict[str, Any]]] = {}
    for it in items:
        by_day.setdefault(it["date"], []).append(it)
    weeks = []
    for week in _calendar.Calendar(firstweekday=0).monthdatescalendar(first.year, first.month):
        weeks.append([{"date": d, "in_month": d.month == first.month, "today": d == today, "entries": by_day.get(d, [])} for d in week])
    return weeks


@router.get("/calendar", include_in_schema=False)
def calendar_page(request: Request, month: str = ""):
    store = get_store(request)
    search = store.current_search()
    first = _month(month)
    today = helpers.today()
    nxt = helpers.add_months(first, 1)
    items: list[dict[str, Any]] = []
    weeks: list[list[dict[str, Any]]] = []
    if search is not None:
        weeks = month_weeks(first, calendar_items(store, search["id"], weeks_start(first), weeks_end(first)), today)
        items = calendar_items(store, search["id"], first, nxt)
    agenda: list[dict[str, Any]] = []
    for it in items:
        if not agenda or agenda[-1]["date"] != it["date"]:
            agenda.append({"date": it["date"], "entries": []})
        agenda[-1]["entries"].append(it)
    return render(request, "calendar.html", search=search, first=first, month_label=first.strftime("%B %Y"),
                  prev_month=helpers.add_months(first, -1).strftime("%Y-%m"), next_month=nxt.strftime("%Y-%m"),
                  is_current=first == helpers.month_start(today), weeks=weeks, agenda=agenda, weekdays=WEEKDAYS, today=today,
                  count=len(items))


def weeks_start(first: date) -> date:
    return helpers.week_start(first)


def weeks_end(first: date) -> date:
    last = first.replace(day=_calendar.monthrange(first.year, first.month)[1])
    return helpers.week_start(last) + timedelta(days=7)


@router.get("/calendar.ics", include_in_schema=False)
def calendar_ics(request: Request):
    store = get_store(request)
    search = store.current_search()
    items = calendar_items(store, search["id"]) if search else []
    places = {p["id"]: p for p in store.list_places(search["id"])} if search else {}
    body = ics.build_calendar(ics_items(items, places))
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="property-helper.ics"'})


# --------------------------------------------------------------------------- tours
def _tour_or_404(store: Store, tour_id: int) -> dict[str, Any]:
    try:
        return store.get_tour(tour_id)
    except NotFound:
        raise HTTPException(404, "That tour doesn't exist (it may have been deleted).") from None


def _place_or_404(store: Store, place_id: int) -> dict[str, Any]:
    try:
        return store.get_place(place_id)
    except NotFound:
        raise HTTPException(404, "That place doesn't exist (it may have been deleted).") from None


def _starts_at(day: str, clock: str) -> str:
    """'2027-07-30' and '14:30' as one local date and time; a blank time means 10:00."""
    day, clock = (day or "").strip(), (clock or "").strip() or "10:00"
    try:
        datetime.strptime(f"{day} {clock}", "%Y-%m-%d %H:%M")
    except ValueError:
        raise ValueError("Pick the day and the time of the tour.") from None
    return f"{day}T{clock}"


@router.post("/places/{place_id}/tours", include_in_schema=False)
async def book_tour(request: Request, place_id: int):
    store = get_store(request)
    _place_or_404(store, place_id)
    form = await request.form()
    try:
        store.add_tour(place_id, _starts_at(str(form.get("day", "")), str(form.get("time", ""))),
                       duration_minutes=form.get("duration_minutes") or 30, with_whom=str(form.get("with_whom", "")),
                       where_note=str(form.get("where_note", "")))
    except ValueError as exc:
        return redirect(f"/places/{place_id}#tours", error=str(exc))
    return redirect(f"/places/{place_id}#tours", notice="Tour booked. It shows on Today and the Calendar.")


@router.post("/tours/{tour_id}/status", include_in_schema=False)
async def tour_status(request: Request, tour_id: int):
    store = get_store(request)
    tour = _tour_or_404(store, tour_id)
    form = await request.form()
    status = str(form.get("status", ""))
    try:
        store.update_tour(tour_id, status=status)
    except ValueError as exc:
        return redirect(f"/places/{tour['place_id']}#tours", error=str(exc))
    said = {"done": "Marked done.", "cancelled": "Tour cancelled.", "booked": "Back to booked."}.get(status, "Saved.")
    return redirect(f"/places/{tour['place_id']}#tours", notice=said)


def tour_checklist_from_form(tour: dict[str, Any], form: Any) -> dict[str, dict[str, str]]:
    """The checklist after the form: items are read by position (``state_0``, ``note_0``...) against the tour's own
    item names (then the defaults it lacks), so a form can only change items that exist."""
    names = list(tour["checklist"].keys()) or list(TOUR_ITEMS)
    out: dict[str, dict[str, str]] = {}
    for i, name in enumerate(names):
        old = tour["checklist"].get(name) or {"state": "", "note": ""}
        state = str(form.get(f"state_{i}", old.get("state", ""))).lower()
        out[name] = {"state": state if state in ("ok", "issue", "") else "", "note": str(form.get(f"note_{i}", old.get("note", "")))}
    return out


@router.post("/tours/{tour_id}/details", include_in_schema=False)
async def tour_details(request: Request, tour_id: int):
    store = get_store(request)
    tour = _tour_or_404(store, tour_id)
    form = await request.form()
    try:
        store.update_tour(tour_id, checklist=tour_checklist_from_form(tour, form), rating=str(form.get("rating", "")),
                          notes=str(form.get("notes", "")))
    except ValueError as exc:
        return redirect(f"/places/{tour['place_id']}#tours", error=str(exc))
    return redirect(f"/places/{tour['place_id']}#tours", notice="Saved the tour notes.")


@router.post("/tours/{tour_id}/delete", include_in_schema=False)
async def tour_delete(request: Request, tour_id: int):
    store = get_store(request)
    tour = _tour_or_404(store, tour_id)
    form = await request.form()
    if str(form.get("confirm", "")) != "yes":
        return redirect(f"/places/{tour['place_id']}#tours", error="Tick the box to confirm. Deleting a tour can't be undone.")
    store.delete_tour(tour_id)
    return redirect(f"/places/{tour['place_id']}#tours", notice="Tour deleted.")
