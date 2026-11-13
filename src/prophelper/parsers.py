"""Read a pasted listing (and its link) into fields. Runs on this computer and never opens the link.

``parse_listing(text, url)`` returns a dict of field -> value for the fields it could find. Keys are the same as the
place fields (``price``, ``beds``, ``baths``, ``sqft``, ``laundry``, ``dishwasher``, ``pets``, ``parking``,
``address``, ``source``, ``title``, ``utilities_included``, ``deposit``, ``year_built``, ``available_from``...). A
missing key means "not found", never a guess. Another module may replace the body with a better parser: keep the
signature and the shape of the result.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any
from urllib.parse import urlsplit

KNOWN_SITES = {
    "zillow.com": "Zillow", "apartments.com": "Apartments.com", "craigslist.org": "Craigslist", "facebook.com": "Facebook",
    "trulia.com": "Trulia", "redfin.com": "Redfin", "realtor.com": "Realtor.com", "rent.com": "Rent.com",
    "hotpads.com": "HotPads", "zumper.com": "Zumper", "apartmentlist.com": "Apartment List", "padmapper.com": "PadMapper",
    "streeteasy.com": "StreetEasy", "loopnet.com": "LoopNet", "homes.com": "Homes.com", "cozy.co": "Cozy",
}
_MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
_STREET = (r"(?:st|street|ave|avenue|rd|road|dr|drive|blvd|boulevard|ln|lane|ct|court|pl|place|way|cir|circle|pkwy|parkway|"
           r"ter|terrace|trl|trail|hwy|highway)")
_ADDRESS = re.compile(r"\b(\d{1,6}\s+(?:(?:\d{1,3}(?:st|nd|rd|th)|[A-Za-z.']+)\s+){1,4}?" + _STREET +
                      r"\b\.?(?:,?\s*(?:#|apt\.?|unit|suite|ste)\s*[A-Za-z0-9-]+)?(?:,\s*[A-Za-z .'-]+,?\s*[A-Z]{2}\b(?:\s+\d{5})?)?)", re.I)


def site_name(url: str | None) -> str:
    """'Zillow' for a zillow.com link, else the host without 'www.' ('rentmaplerow.com'). '' for no usable link."""
    try:
        host = (urlsplit(str(url or "").strip()).hostname or "").lower()
    except ValueError:
        return ""
    if not host and url and "." in str(url).split("/")[0]:
        try:
            host = (urlsplit("https://" + str(url).strip()).hostname or "").lower()
        except ValueError:
            host = ""
    host = host[4:] if host.startswith("www.") else host
    if not host:
        return ""
    for domain, name in KNOWN_SITES.items():
        if host == domain or host.endswith("." + domain):
            return name
    return host


def _money(s: str) -> float | None:
    try:
        return float(s.replace(",", "").replace("$", ""))
    except ValueError:
        return None


def _price(text: str) -> float | None:
    """The monthly rent: a $ amount near 'per month', '/mo' or 'rent', else the first plausible $ amount."""
    patterns = [
        r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,6})(?:\.\d{2})?\s*(?:/|per|a|each)?\s*(?:mo\b|month|mth)",
        r"(?:rent|price|asking)[^$\d\n]{0,20}\$\s?(\d{1,3}(?:,\d{3})+|\d{3,6})",
        r"\$\s?(\d{1,3}(?:,\d{3})+|\d{3,6})\b(?!\s*(?:k\b|deposit|fee|application))",
    ]
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            v = _money(m.group(1))
            if v and 300 <= v <= 20000:
                return v
    return None


def _buy_price(text: str) -> float | None:
    m = re.search(r"\$\s?(\d{1,3}(?:,\d{3}){1,2})\b", text)
    v = _money(m.group(1)) if m else None
    return v if v and v >= 20000 else None


def parse_listing(text: str = "", url: str = "") -> dict[str, Any]:
    """Pull what a pasted listing says. Returns only the fields found."""
    text = text or ""
    low = text.lower()
    out: dict[str, Any] = {}
    src = site_name(url)
    if src:
        out["source"] = src
    price = _price(text)
    if price is not None:
        out["price"] = price
    elif (bp := _buy_price(text)) is not None and not re.search(r"\b(per month|/mo|rent)\b", low):
        out["price"] = bp

    if re.search(r"\bstudio\b", low) and not re.search(r"\b\d+\s*(?:bed|br|bd)", low):
        out["beds"] = 0
    else:
        m = re.search(r"\b(\d+(?:\.\d)?)\s*[- ]?(?:bed(?:room)?s?|br|bd|bdrm)\b", low) or re.search(r"\b(\d)\s*b(?:\s*/\s*|\s+)\d(?:\.\d)?\s*b\b", low)
        if m:
            out["beds"] = float(m.group(1))
    m = re.search(r"\b(\d+(?:\.\d)?)\s*[- ]?(?:bath(?:room)?s?|ba|bth)\b", low) or re.search(r"\b\d\s*b(?:\s*/\s*|\s+)(\d(?:\.\d)?)\s*b\b", low)
    if m:
        out["baths"] = float(m.group(1))
    m = re.search(r"\b(\d{3,5}(?:,\d{3})?)\s*(?:sq\.?\s*ft|sqft|square feet|sf)\b", low)
    if m:
        out["sqft"] = int(m.group(1).replace(",", ""))

    if re.search(r"\b(?:in[- ]unit|in[- ]home|washer\s*(?:/|and|&)\s*dryer|w/d)\b(?![^.]{0,25}(?:hookups? only|not included))", low) \
            and not re.search(r"no (?:in[- ]unit )?(?:washer|laundry)", low):
        out["laundry"] = "in_unit"
    elif re.search(r"\b(?:laundry (?:room|facilit|on[- ]?site|in (?:the )?building)|on[- ]site laundry|shared laundry|laundry facilities)", low):
        out["laundry"] = "in_building"
    elif re.search(r"\bno laundry\b", low):
        out["laundry"] = "none"
    if re.search(r"\bno dishwasher\b", low):
        out["dishwasher"] = 0
    elif re.search(r"\bdish ?washer\b", low):
        out["dishwasher"] = 1

    if re.search(r"\bno pets\b|pets not allowed|not pet[- ]friendly", low):
        out["pets"] = "none"
    elif re.search(r"\bcats? and dogs?\b|\bdogs? and cats?\b|pet[- ]friendly|pets (?:ok|allowed|welcome)", low):
        out["pets"] = "both"
    elif re.search(r"\bcats? (?:ok|allowed|welcome)|\bcat[- ]friendly", low):
        out["pets"] = "cats"
    elif re.search(r"\bdogs? (?:ok|allowed|welcome)|\bdog[- ]friendly", low):
        out["pets"] = "dogs"

    if re.search(r"\b(?:attached |private |heated )?garage\b(?! door)", low) and not re.search(r"no garage", low):
        out["parking"] = "garage"
    elif re.search(r"\bcarport|covered parking", low):
        out["parking"] = "covered"
    elif re.search(r"\b(?:off[- ]street|surface|free|assigned|reserved|on[- ]site|private) parking|parking (?:lot|included|available)|driveway", low):
        out["parking"] = "lot"
    elif re.search(r"\bstreet parking\b", low):
        out["parking"] = "street"
    elif re.search(r"\bno parking\b", low):
        out["parking"] = "none"
    m = re.search(r"parking[^$\n.]{0,25}\$\s?(\d{2,4})\s*(?:/|per|a)?\s*(?:mo|month)", low)
    if m:
        out["parking_cost"] = float(m.group(1))

    m = re.search(r"(?:security )?deposit[^$\d\n]{0,20}\$\s?(\d{1,3}(?:,\d{3})+|\d{2,5})", low)
    if m and (v := _money(m.group(1))):
        out["deposit"] = v
    m = re.search(r"application fee[^$\d\n]{0,15}\$\s?(\d{1,4})", low)
    if m:
        out["application_fee"] = float(m.group(1))
    m = re.search(r"pet rent[^$\d\n]{0,15}\$\s?(\d{1,4})", low)
    if m:
        out["pet_rent"] = float(m.group(1))
    m = re.search(r"(?:built in|year built|built)[^0-9]{0,10}((?:19|20)\d{2})\b", low)
    if m:
        out["year_built"] = int(m.group(1))
    if re.search(r"\b(?:all )?utilities (?:are )?included|water,? (?:sewer,? )?(?:and )?trash (?:is |are )?(?:included|paid)", low):
        out["utilities_included"] = "all utilities included" if re.search(r"\ball utilities (?:are )?included", low) else "some utilities included"

    m = re.search(r"(?:available|move[- ]in|avail\.?)[^0-9a-z]{0,12}(?:(\d{4})-(\d{2})-(\d{2})|(\d{1,2})/(\d{1,2})/(\d{2,4})|"
                  r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})?)", low)
    if m:
        try:
            if m.group(1):
                out["available_from"] = f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
            elif m.group(4):
                y = int(m.group(6)); y += 2000 if y < 100 else 0
                out["available_from"] = date(y, int(m.group(4)), int(m.group(5))).isoformat()
            else:
                y = int(m.group(9)) if m.group(9) else date.today().year
                d = date(y, _MONTHS[m.group(7)], int(m.group(8)))
                if not m.group(9) and d < date.today():
                    d = date(y + 1, d.month, d.day)
                out["available_from"] = d.isoformat()
        except ValueError:
            pass

    m = _ADDRESS.search(text)
    if m:
        out["address"] = " ".join(m.group(1).split()).rstrip(",.")
    title = _title(text, out)
    if title:
        out["title"] = title
    return out


def _title(text: str, found: dict[str, Any]) -> str:
    """A short title: the first line of the paste when it looks like a heading, else the address."""
    for line in text.splitlines():
        line = line.strip()
        if 4 <= len(line) <= 90 and not line.startswith(("http", "$")) and not re.fullmatch(r"[\d\s$,./-]+", line) \
                and not re.search(r"\b(?:call|text|email|contact|apply)\b.*\d{3}", line.lower()):
            return line
        if line:
            break
    return found.get("address", "").split(",")[0] if found.get("address") else ""
