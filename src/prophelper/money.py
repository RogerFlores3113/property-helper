"""True monthly cost for rent and for buying (DESIGN section 5). Pure: no database, no web.

Rent: price + utilities_estimate + parking_cost + pet_rent + other_monthly_fees
      + (application_fee + move_in_fees + broker_fee + pet_fee) / lease_months (12 when empty).
The deposit is shown but not spread (it comes back).
Buy:  monthly principal and interest + property_tax / 12 + insurance / 12 + hoa. An estimate, not advice.

Each function returns ``{"total", "lines", "missing", "notes", ...}``. ``total`` is None when the main price is
missing. ``lines`` is ``[{"key", "label", "amount", "note"}]`` in display order, ``missing`` names the numbers that
are not filled in (so the page can say "add the utilities estimate").
"""
from __future__ import annotations

from typing import Any

DEFAULT_LEASE_MONTHS = 12
DEFAULT_BUY = {"down_payment_pct": 20.0, "mortgage_rate": 6.5, "loan_years": 30}
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
            lines.append(_line("utilities", "Utilities (your estimate)", None, "not filled in"))
    else:
        lines.append(_line("utilities", "Utilities (your estimate)", util, str(place.get("utilities_included") or "")))

    parking = num(place.get("parking_cost"))
    if parking is None and str(place.get("parking") or "") in PRIVATE_PARKING:
        missing.append("parking cost")
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
            "lease_months": months, "one_time_total": _r(one_total)}


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
    lines: list[dict[str, Any]] = []
    if price is None:
        missing.append("asking price")
        lines.append(_line("loan", "Loan payment (principal and interest)", None, "needs the asking price"))
        pi = None
    else:
        down = price * cfg["down_payment_pct"] / 100
        pi = monthly_payment(price - down, cfg["mortgage_rate"], cfg["loan_years"])
        lines.append(_line("loan", "Loan payment (principal and interest)", pi,
                           f"{cfg['down_payment_pct']:g}% down, {cfg['mortgage_rate']:g}% rate, {cfg['loan_years']:g} years"))
    tax, ins, hoa = num(place.get("property_tax")), num(place.get("insurance")), num(place.get("hoa"))
    for key, label, val, per in (("tax", "Property tax", tax, 12), ("insurance", "Insurance", ins, 12)):
        if val is None:
            missing.append(label.lower() + " (per year)")
            lines.append(_line(key, label, None, "not filled in"))
        else:
            lines.append(_line(key, label, val / per, f"${val:,.0f} a year"))
    if hoa is None:
        missing.append("HOA (per month)")
        lines.append(_line("hoa", "HOA", None, "not filled in"))
    else:
        lines.append(_line("hoa", "HOA", hoa))
    total = None if pi is None else _r(sum(l["amount"] or 0 for l in lines))
    return {"mode": "buy", "total": total, "lines": lines, "missing": missing,
            "notes": ["An estimate to compare places, not financial advice."], "deposit": None,
            "down_payment": None if price is None else _r(price * cfg["down_payment_pct"] / 100), "settings": cfg}


def true_monthly_cost(place: dict[str, Any], mode: str = "rent", settings: dict[str, Any] | None = None) -> dict[str, Any]:
    """Rent or buy breakdown depending on the search's mode."""
    return buy_cost(place, settings) if mode == "buy" else rent_cost(place)
