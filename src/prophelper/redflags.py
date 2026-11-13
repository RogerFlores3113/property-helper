"""A local, no-AI "things to check" pass over a place (keyword and price rules). Pure: no database, no web.

It never says a listing IS a scam. It lists signs worth a second look, in plain words. The AI red-flag check (when
the user asks for it) adds to this.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Any, Iterable

_PAYMENT = re.compile(r"\b(wire (?:the |me |us )?(?:deposit|money|funds|payment)|wire transfer|western union|moneygram|"
                      r"gift ?cards?|bitcoin|crypto(?:currency)?|zelle|cash ?app|venmo|apple pay|send (?:the |your )?deposit)\b", re.I)
_ABROAD = re.compile(r"\b(out of (?:the )?(?:country|town|state)|owner (?:is )?(?:abroad|overseas|traveling|travelling)|"
                     r"(?:abroad|overseas|missionary|deployed)|can'?t (?:show|meet|tour)|unable to (?:show|meet))\b", re.I)
_PRESSURE = re.compile(r"\b(act (?:now|fast|today)|decide today|must (?:decide|respond|pay) (?:today|now|immediately)|"
                       r"won'?t last|many (?:people|applicants) (?:are )?(?:interested|waiting)|first come|hurry)\b", re.I)
_BEFORE_SHOWING = re.compile(r"\b(deposit|payment|fee)\b[^.]{0,60}\b(before|prior to|to (?:secure|hold|see|view))\b[^.]{0,40}"
                             r"\b(show|showing|viewing|tour|see|keys?|visit)", re.I)
_CODES = re.compile(r"\b(keys? (?:will be )?(?:mailed|shipped|sent)|mail(?:ed)? (?:you )?the keys)\b", re.I)
PRICE_FLOOR_RATIO = 0.55  # under this share of the typical price in the same search is "far under"


def local_flags(place: dict[str, Any], peer_prices: Iterable[float] = ()) -> list[str]:
    """Plain-words signs to check on this place. ``peer_prices``: prices of the other places in the same search."""
    text = " ".join(str(place.get(k) or "") for k in ("listing_text", "title", "notes", "ai_notes"))
    flags: list[str] = []
    if _PAYMENT.search(text):
        flags.append("It asks for payment in a way that is hard to undo (wire, gift card, crypto or a payment app). "
                     "Real landlords take a check or a normal online portal after you have seen the place.")
    if _BEFORE_SHOWING.search(text):
        flags.append("It asks for a deposit or fee before you have seen the place. Don't pay before a showing and a lease you have read.")
    if _ABROAD.search(text):
        flags.append("The owner is away or can't show the place. A scam often says the owner is out of the country.")
    if _PRESSURE.search(text):
        flags.append("It pressures you to decide today. A real place can wait for a tour.")
    if _CODES.search(text):
        flags.append("It says the keys will be mailed to you. Don't pay for a place you can't visit.")
    price = place.get("price")
    peers = [float(p) for p in peer_prices if p]
    if price and len(peers) >= 3:
        typical = median(peers)
        if typical and float(price) < PRICE_FLOOR_RATIO * typical:
            flags.append(f"The price is far under the other places in this search (about ${typical:,.0f} is typical here). "
                         "A price that is too good to be true often is.")
    address = str(place.get("address") or "").strip()
    if address and not re.search(r"\d", address.split(",")[0]):
        flags.append("The address has no street number. Ask for the exact address before you go anywhere or pay anything.")
    if not address and not place.get("lat") and place.get("listing_text"):
        flags.append("There is no address yet. Ask for one before you go anywhere or pay anything.")
    return flags
