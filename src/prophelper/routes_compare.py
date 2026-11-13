"""Compare 2 to 4 places side by side.

    GET /compare                 a picker (checkboxes of the current search's places)
    GET /compare?ids=3,5,8       the comparison (also ?ids=3&ids=5 from the picker)

Nothing is written. Places from different searches can be compared; each one's cost uses its own search's mode.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from . import compare, enrich
from .deps import get_store, render
from .store import NotFound

router = APIRouter()


@router.get("/compare", include_in_schema=False)
def compare_page(request: Request, ids: list[str] | None = Query(default=None)):
    store = get_store(request)
    search = store.current_search()
    options = store.list_places(search["id"]) if search else []
    ctx: dict[str, Any] = {"search": search, "options": options, "picked": [], "places": [], "sections": [], "summary": [],
                           "problem": "", "missing": 0}
    if not ids:
        return render(request, "compare.html", **ctx)
    wanted: list[int] = []
    try:
        wanted = compare.parse_ids(ids)
        found, missing = [], 0
        for pid in wanted:
            try:
                found.append(store.get_place(pid))
            except NotFound:
                missing += 1
        compare.check_count(len(found))
    except compare.CompareError as exc:
        ctx.update(problem=str(exc), picked=wanted)
        return render(request, "compare.html", status_code=400, **ctx)
    places = []
    for p in found:
        places.append(enrich.enrich_places(store, store.get_search(p["search_id"]), [p])[0])
    sections = compare.build_rows(places)
    ctx.update(places=places, sections=sections, summary=compare.summary_lines(places, sections), picked=[p["id"] for p in places],
               missing=missing)
    return render(request, "compare.html", **ctx)
