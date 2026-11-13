"""True monthly cost for rent and for buying (DESIGN section 5). Pure: no database, no web.

Rent: price + utilities_estimate + parking_cost + pet_rent + other_monthly_fees
      + (application_fee + move_in_fees + broker_fee + pet_fee) / lease_months (12 when empty).
The deposit is shown but not spread (it comes back).
Buy:  monthly principal and interest + PMI (when the down payment is under 20%) + property_tax / 12 + insurance / 12 + hoa.
      An estimate, not advice. ``cash_to_close`` is kept apart from the monthly cost: down payment + closing costs
      (the number entered, else an estimate of closing_cost_pct of the price) + a special assessment the buyer pays
      (treated as one amount, not billed monthly).

Each function returns ``{"total", "lines", "missing", "notes", ...}``. ``total`` is None when the main price is
missing. ``lines`` is ``[{"key", "label", "amount", "note"}]`` in display order, ``missing`` names the numbers that
are not filled in (so the page can say "add the utilities estimate"). ``uncounted`` names the costs left out of the
total in short words ("insurance", "utilities") and ``headline`` is the one line to show next to the total, such as
"$2,414/mo, insurance not counted yet". ``per_person`` is the total split over ``people`` (only when people > 1).
"""
from __future__ import annotations

from typing import Any

DEFAULT_LEASE_MONTHS = 12
DEFAULT_BUY = {"down_payment_pct": 20.0, "mortgage_rate": 6.5, "loan_years": 30, "pmi_rate_pct": 0.5,
               "closing_cost_pct": 3.0}
PMI_BELOW_PCT = 20.0  # mortgage insurance is estimated when the down payment is under this share of the price
PRIVATE_PARKING = ("garage", "covered", "lot")


def num(value: Any) -> float | None:
    """A number from a stored value, or None for blank or not a number."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if out == out else None  # NaN is not a number


def _r(x: float) -> float:
    return round(x + 1e-9, 2)


def _line(key: str, label: str, amount: float | None, note: str = "") -> dict[str, Any]:
    return {"key": key, "label": label, "amount": None if amount is None else _r(amount), "note": note}


def utilities_covered(place: dict[str, Any]) -> bool:
    text = str(place.get("utilities_included") or "").lower()
    return any(w in text for w in ("all utilities", "everything", "all included", "all inclusive", "all-inclusive"))


def rent_cost(place: dict[str, Any]) -> dict[str, Any]:
    """The true monthly cost of renting this place, line by line."""
    price = num(place.get("price"))
    missing: list[str] = []
    uncounted: list[str] = []
    notes: list[str] = []
    lines: list[dict[str, Any]] = []
    if price is None:
        missing.append("monthly rent")
    lines.append(_line("price", "Rent", price))

    util = num(place.get("utilities_estimate"))
    if util is None:
        if utilities_covered(place):
            lines.append(_line("utilities", "Utilities", 0, "included in the rent"))
        else:
            missing.append("utilities estimate")
            uncounted.append("utilities")
            lines.append(_line("utilities", "Utilities", None, "not filled in"))
    else:
        note = "A guess, not from the listing"
        if place.get("utilities_included"):
            note += f". The listing includes: {place['utilities_included']}"
        line = _line("utilities", "Utilities (a guess)", util, note)
        line["estimated"] = True
        lines.append(line)

    parking = num(place.get("parking_cost"))
    if parking is None and str(place.get("parking") or "") in PRIVATE_PARKING:
        missing.append("parking cost")
        uncounted.append("parking")
        lines.append(_line("parking", "Parking", None, "not filled in"))
    else:
        lines.append(_line("parking", "Parking", parking or 0))
    pet_rent = num(place.get("pet_rent")) or 0
    other = num(place.get("other_monthly_fees")) or 0
    lines.append(_line("pet_rent", "Pet rent", pet_rent))
    lines.append(_line("other", "Other monthly fees", other))

    months = place.get("lease_months")
    try:
        months = int(months) if months not in (None, "") and int(months) > 0 else DEFAULT_LEASE_MONTHS
    except (TypeError, ValueError):
        months = DEFAULT_LEASE_MONTHS
    one_time = {"application_fee": "Application fee", "move_in_fees": "Move-in fees", "broker_fee": "Broker fee",
                "pet_fee": "Pet fee"}
    one_total = sum(num(place.get(k)) or 0 for k in one_time)
    spread = one_total / months
    detail = ", ".join(f"{label.lower()} ${num(place.get(k)):,.0f}" for k, label in one_time.items()
                       if num(place.get(k)))
    lines.append(_line("one_time", f"One-time fees spread over {months} months", spread,
                       detail or "none entered"))
    if not place.get("lease_months"):
        notes.append(f"Lease length not filled in, so one-time fees are spread over {DEFAULT_LEASE_MONTHS} months.")
    deposit = num(place.get("deposit"))
    total = None if price is None else _r(sum(l["amount"] or 0 for l in lines))
    if deposit:
        notes.append(f"Deposit ${deposit:,.0f} is not included in the monthly cost because it comes back.")
    return {"mode": "rent", "total": total, "lines": lines, "missing": missing, "notes": notes, "deposit": deposit,
            "lease_months": months, "one_time_total": _r(one_total), "uncounted": uncounted,
            "cash_at_move_in": cash_at_move_in(place)}


def cash_at_move_in(place: dict[str, Any]) -> dict[str, Any] | None:
    """Cash needed on move-in day for a rental: first month, last month (when the listing asks for it), deposit,
    application fee and the other one-time fees. Kept apart from the true monthly cost (the last month's rent and the
    deposit are not a yearly cost). None when there is no rent to build it on."""
    rent = num(place.get("price"))
    if not rent:
        return None
    last = False
    try:
        from .parsers import _move_in_months
        last = bool(_move_in_months(str(place.get("listing_text") or ""))[0])
    except Exception:  # the listing text is only a hint
        pass
    parts = [("First month's rent", rent)]
    if last:
        parts.append(("Last month's rent", rent))
    for key, label in (("deposit", "Deposit"), ("application_fee", "Application fee"), ("move_in_fees", "Move-in fees"),
                       ("broker_fee", "Broker fee"), ("pet_fee", "Pet fee"), ("pet_deposit", "Pet deposit (comes back)")):
        v = num(place.get(key))
        if v:
            parts.append((label, v))
    return {"total": _r(sum(v for _, v in parts)), "parts": [{"label": a, "amount": b} for a, b in parts]}


def _listing_estimate_note(place: dict[str, Any], total: float | None, lines: list[dict[str, Any]]) -> str:
    """"The listing estimates $2,310/mo; ours is $2,708 because it counts PMI and HOA." Empty when the listing quotes
    no payment of its own (it is read from the saved listing text, so no column is needed)."""
    text = str(place.get("listing_text") or "")
    if total is None or "pay" not in text.lower():
        return ""
    try:
        from .parsers import listing_estimated_payment
        est = listing_estimated_payment(text)
    except Exception:  # the listing text is only a hint
        return ""
    if not est:
        return ""
    names = {"pmi": "PMI", "tax": "property tax", "insurance": "insurance", "hoa": "HOA"}
    counted = [names[l["key"]] for l in lines if l["key"] in names and (l["amount"] or 0) > 0]
    if abs(total - est) < 1:
        return f"The listing estimates {_dollars(est)}/mo, about the same as ours."
    if total > est:
        why = f" because ours counts {_join_words(counted)}" if counted else ""
        return f"The listing estimates {_dollars(est)}/mo; ours is {_dollars(total)}{why}."
    return (f"The listing estimates {_dollars(est)}/mo; ours is {_dollars(total)}. "
            "Listings often count costs we don't know yet, so ask what theirs includes.")


def cash_to_close(place: dict[str, Any], cfg: dict[str, float] | None = None) -> dict[str, Any] | None:
    """Cash a buyer needs at closing: down payment, closing costs (entered, else a guess of closing_cost_pct of the
    price, marked ``estimated``) and a special assessment when the buyer pays it. None without a price."""
    cfg = cfg or dict(DEFAULT_BUY)
    price = num(place.get("price"))
    if not price:
        return None
    down = price * cfg["down_payment_pct"] / 100
    parts: list[dict[str, Any]] = [{"label": "Down payment", "amount": _r(down), "estimated": False}]
    closing = num(place.get("closing_costs"))
    if closing is None:
        pct = cfg.get("closing_cost_pct", DEFAULT_BUY["closing_cost_pct"])
        parts.append({"label": f"Closing costs (a guess: {pct:g}% of the price)", "amount": _r(price * pct / 100), "estimated": True})
    else:
        parts.append({"label": "Closing costs", "amount": _r(closing), "estimated": False})
    sa = num(place.get("special_assessment"))
    if sa and str(place.get("special_assessment_payer") or "") == "buyer":
        parts.append({"label": "Special assessment (you pay it)", "amount": _r(sa), "estimated": False})
    return {"total": _r(sum(p["amount"] for p in parts)), "parts": parts,
            "has_estimate": any(p["estimated"] for p in parts)}


def monthly_payment(principal: float, annual_rate_pct: float, years: float) -> float:
    """Principal and interest per month for a fixed-rate loan."""
    n = int(round(years * 12))
    if n <= 0 or principal <= 0:
        return 0.0
    r = annual_rate_pct / 100 / 12
    if r == 0:
        return principal / n
    return principal * r / (1 - (1 + r) ** -n)


def buy_settings(settings: dict[str, Any] | None = None) -> dict[str, float]:
    """The buyer defaults (down payment percent, mortgage rate, loan years) from settings, with fallbacks."""
    out: dict[str, float] = dict(DEFAULT_BUY)
    for k in DEFAULT_BUY:
        v = num((settings or {}).get(k))
        if v is not None and v >= 0:
            out[k] = v
    return out


def buy_cost(place: dict[str, Any], settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """The estimated monthly cost of buying: loan payment, property tax, insurance, HOA."""
    cfg = buy_settings(settings)
    price = num(place.get("price"))
    missing: list[str] = []
    uncounted: list[str] = []
    lines: list[dict[str, Any]] = []
    down = loan = pmi = None
    notes = ["An estimate to compare places, not financial advice."]
    if price is None:
        missing.append("asking price")
        lines.append(_line("loan", "Loan payment (principal and interest)", None, "needs the asking price"))
        pi = None
    else:
        down = price * cfg["down_payment_pct"] / 100
        loan = price - down
        pi = monthly_payment(loan, cfg["mortgage_rate"], cfg["loan_years"])
        lines.append(_line("loan", "Loan payment (principal and interest)", pi,
                           f"Loan {_dollars(loan)} after {_dollars(down)} down ({cfg['down_payment_pct']:g}%), "
                           f"{cfg['mortgage_rate']:g}% rate, {cfg['loan_years']:g} years"))
        if cfg["down_payment_pct"] < PMI_BELOW_PCT:
            pmi = loan * cfg["pmi_rate_pct"] / 100 / 12
            lines.append(_line("pmi", "Mortgage insurance (PMI), an estimate", pmi,
                               f"{cfg['pmi_rate_pct']:g}% of the loan a year, because the down payment is under {PMI_BELOW_PCT:g}%"))
            notes.append("PMI is a rough guess. Your lender's quote decides the real number.")
    tax, ins, hoa = num(place.get("property_tax")), num(place.get("insurance")), num(place.get("hoa"))
    for key, label, val, per in (("tax", "Property tax", tax, 12), ("insurance", "Insurance", ins, 12)):
        if val is None:
            missing.append(label.lower() + " (per year)")
            uncounted.append(label.lower())
            lines.append(_line(key, label, None, "not filled in"))
        else:
            lines.append(_line(key, label, val / per, f"${val:,.0f} a year"))
    if hoa is None:
        missing.append("HOA (per month)")
        uncounted.append("HOA")
        lines.append(_line("hoa", "HOA", None, "not filled in"))
    else:
        lines.append(_line("hoa", "HOA", hoa))
    total = None if pi is None else _r(sum(l["amount"] or 0 for l in lines))
    cash = cash_to_close(place, cfg)
    sa, payer = num(place.get("special_assessment")), str(place.get("special_assessment_payer") or "")
    if sa and payer == "buyer":
        notes.append(f"The special assessment ({_dollars(sa)}, paid by you) is counted once in the cash to close, not in the monthly cost.")
    elif sa and payer == "seller":
        notes.append(f"A special assessment of {_dollars(sa)} is paid by the seller, so it is not counted.")
    elif sa:
        notes.append(f"A special assessment of {_dollars(sa)} is listed but who pays it is not filled in, so it is not counted. Ask.")
    listing_note = _listing_estimate_note(place, total, lines)
    return {"mode": "buy", "listing_estimate_note": listing_note, "total": total, "lines": lines, "missing": missing, "uncounted": uncounted,
            "notes": notes, "deposit": None,
            "down_payment": None if down is None else _r(down), "loan_amount": None if loan is None else _r(loan),
            "pmi": None if pmi is None else _r(pmi), "settings": cfg, "cash_to_close": cash}


def _dollars(n: float) -> str:
    return f"${n:,.0f}"


def _join_words(items: list[str]) -> str:
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " and " + items[-1]


def headline(cost: dict[str, Any], people: int = 1) -> str:
    """The one line next to the total: '$2,414/mo, insurance not counted yet' (and '$807 each' when people share it)."""
    total = cost.get("total")
    if total is None:
        return "Cost unknown"
    text = f"{_dollars(total)}/mo"
    unc = list(cost.get("uncounted") or [])
    if unc:
        text += f", {_join_words(unc)} not counted yet"
    if people and people > 1:
        text += f" ({_dollars(total / people)} each for {people} people)"
    return text


def true_monthly_cost(place: dict[str, Any], mode: str = "rent", settings: dict[str, Any] | None = None,
                      people: Any = 1) -> dict[str, Any]:
    """Rent or buy breakdown depending on the search's mode. ``people`` (people sharing the cost) adds
    ``people`` and, when more than one, ``per_person``. ``headline`` is the line to show next to the total."""
    out = buy_cost(place, settings) if mode == "buy" else rent_cost(place)
    try:
        n = max(1, int(people or 1))
    except (TypeError, ValueError):
        n = 1
    out["people"] = n
    out["per_person"] = _r(out["total"] / n) if out["total"] is not None and n > 1 else None
    out["headline"] = headline(out, 1)
    out["headline_each"] = headline(out, n)
    return out
