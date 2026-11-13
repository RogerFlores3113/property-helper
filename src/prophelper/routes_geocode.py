"""Opt-in address lookup (OpenStreetMap Nominatim) for places and anchors.

    POST /places/{id}/geocode     look up the place's address, save lat and lng, go back to the page
    POST /anchors/{id}/geocode    the same for an anchor (a saved place for commutes, like Campus or Work)

Only works when "Find map locations for addresses" is on in Settings. See ``geocode.py`` for exactly what is sent.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from . import geocode
from .deps import back, get_store
from .store import NotFound

router = APIRouter()

OFF = "Address lookup is off, so nothing was sent. Turn on \"Find map locations for addresses\" in Settings first."


@router.post("/places/{place_id}/geocode", include_in_schema=False)
def geocode_place(request: Request, place_id: int):
    store = get_store(request)
    try:
        place = store.get_place(place_id)
    except NotFound:
        raise HTTPException(404, "That place doesn't exist (it may have been deleted).") from None
    default = f"/places/{place_id}"
    if not store.get_setting_bool("geocode"):
        return back(request, default, error=OFF)
    if not (place.get("address") or "").strip():
        return back(request, default, error="This place has no street address yet. Save one, then look it up.")
    try:
        lat, lng, name = geocode.lookup(geocode.address_text(place))
        store.update_place(place_id, by="you", lat=lat, lng=lng)
    except (geocode.GeocodeError, ValueError) as exc:
        return back(request, default, error=str(exc))
    return back(request, default, notice=f"Found it and saved the map point ({lat}, {lng})." + (f" OpenStreetMap calls it: {name}" if name else ""))


@router.post("/anchors/{anchor_id}/geocode", include_in_schema=False)
async def geocode_anchor(request: Request, anchor_id: int):
    store = get_store(request)
    try:
        anchor = store.get_anchor(anchor_id)
    except NotFound:
        raise HTTPException(404, "That anchor doesn't exist.") from None
    form = await request.form()
    default = f"/search?id={form.get('search_id')}#anchors" if str(form.get("search_id") or "").isdigit() else "/search#anchors"
    if not store.get_setting_bool("geocode"):
        return back(request, default, error=OFF)
    if not (anchor.get("address") or "").strip():
        return back(request, default, error=f"{anchor['name']} has no address yet. Type one, save it, then look it up.")
    try:
        lat, lng, name = geocode.lookup(geocode.address_text(anchor))
        store.update_anchor(anchor_id, lat=lat, lng=lng)
    except (geocode.GeocodeError, ValueError) as exc:
        return back(request, default, error=str(exc))
    return back(request, default, notice=f"Found {anchor['name']} and saved its map point ({lat}, {lng})." + (f" OpenStreetMap calls it: {name}" if name else ""))
