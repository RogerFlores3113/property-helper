"""The application checklist: one reusable list of what a landlord usually asks for.

    GET  /checklist                      the list, with how many are ready
    POST /checklist/items                add an item
    POST /checklist/items/{id}           save its label and note
    POST /checklist/items/{id}/done      tick it or untick it (value=1 or 0)
    POST /checklist/items/{id}/move      move it up or down (direction=up or down)
    POST /checklist/items/{id}/delete    remove it

The app keeps the list, not copies of the documents.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from .deps import get_store, redirect, render
from .store import NotFound, Store

router = APIRouter()


def _item_or_404(store: Store, item_id: int) -> dict[str, Any]:
    try:
        return store.get_checklist_item(item_id)
    except NotFound:
        raise HTTPException(404, "That checklist item doesn't exist (it may have been removed).") from None


@router.get("/checklist", include_in_schema=False)
def checklist_page(request: Request):
    store = get_store(request)
    items = store.list_checklist()
    return render(request, "checklist.html", items=items, done=sum(1 for i in items if i["done"]))


@router.post("/checklist/items", include_in_schema=False)
async def add_item(request: Request):
    store = get_store(request)
    form = await request.form()
    try:
        store.add_checklist_item(str(form.get("label", "")), str(form.get("note", "")))
    except ValueError as exc:
        return redirect("/checklist", error=str(exc))
    return redirect("/checklist#add", notice="Added.")


@router.post("/checklist/items/{item_id}", include_in_schema=False)
async def save_item(request: Request, item_id: int):
    store = get_store(request)
    _item_or_404(store, item_id)
    form = await request.form()
    try:
        store.update_checklist_item(item_id, label=str(form.get("label", "")), note=str(form.get("note", "")))
    except ValueError as exc:
        return redirect(f"/checklist#item-{item_id}", error=str(exc))
    return redirect(f"/checklist#item-{item_id}", notice="Saved.")


@router.post("/checklist/items/{item_id}/done", include_in_schema=False)
async def set_done(request: Request, item_id: int):
    store = get_store(request)
    _item_or_404(store, item_id)
    form = await request.form()
    on = str(form.get("value", "1")) == "1"
    store.update_checklist_item(item_id, done=on)
    return redirect(f"/checklist#item-{item_id}", notice="Marked ready." if on else "Marked not ready.")


@router.post("/checklist/items/{item_id}/move", include_in_schema=False)
async def move_item(request: Request, item_id: int):
    store = get_store(request)
    _item_or_404(store, item_id)
    form = await request.form()
    store.move_checklist_item(item_id, -1 if str(form.get("direction", "")) == "up" else 1)
    return redirect(f"/checklist#item-{item_id}")


@router.post("/checklist/items/{item_id}/delete", include_in_schema=False)
def delete_item(request: Request, item_id: int):
    store = get_store(request)
    item = _item_or_404(store, item_id)
    store.delete_checklist_item(item_id)
    return redirect("/checklist", notice=f"Removed {item['label']}.")
