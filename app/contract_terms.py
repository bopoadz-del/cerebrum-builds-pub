"""The contract and BOQ as the project's source of record.

Nothing in this module invents a clause number, a rate or a period. The
contract text below is the uploaded source of record; at import it is parsed
into numbered clauses and their stated figures. The BOQ text is likewise the
uploaded bill, parsed into measured items. Code cites what it parsed, so the
same names resolve whatever the uploaded documents say.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

CONTRACT_FILENAME = "3e1eb320b3a140acb0529606ee6d6431_harbourline_contract.pdf"
BOQ_FILENAME = "de42be780f4f4087b8d9520a040a4b78_harbourline_boq.xlsx"

DOCUMENTS: Dict[str, str] = {
    CONTRACT_FILENAME: (
        "HARBOURLINE CIVIL WORKS - CONTRACT EXCERPT (SYNTHETIC - NO CLIENT DATA)\n"
        "Clause 8.2  Time for Completion: 730 days from the Commencement Date.\n"
        "Clause 8.7  Delay Damages: 0.1% of the Accepted Contract Amount per day of\n"
        "delay, capped at 10% of the Accepted Contract Amount.\n"
        "Clause 11.1 Defects Notification Period: 365 days from Taking-Over.\n"
        "Clause 14.3 Retention: 5% of each Interim Payment Certificate, released 50% at\n"
        "Taking-Over and 50% at the end of the Defects Notification Period.\n"
        "Clause 4.2  Performance Security: 10% of the Accepted Contract Amount."
    ),
    BOQ_FILENAME: (
        "# Preliminaries\n"
        "Item\tDescription\tUnit\tQty\tRate (SAR)\n"
        "P1\tSite establishment & temporary facilities\tsum\t1\t185000\n"
        "P2\tSite security & fencing (6 months)\tmonth\t6\t22000\n"
        "P3\tSurvey & setting out\tsum\t1\t48000\n"
        "P4\tProject signboard\tno\t2\t3500\n"
        "P5\tAs-built documentation\tsum\t1\t26000\n"
        "# Earthworks\n"
        "Item\tDescription\tUnit\tQty\tRate (SAR)\n"
        "E1\tBulk excavation to reduced level\tm3\t12500\t38\n"
        "E2\tDisposal of surplus material off-site\tm3\t8200\t25\n"
        "E3\tImported granular fill, compacted\tm3\t6400\t92\n"
        "E4\tTrench excavation for services\tm3\t1850\t55\n"
        "E5\tGeotextile separation layer\tm2\t9600\t14"
    ),
}

_CLAUSE_LINE = re.compile(
    r"^Clause\s+([0-9]+(?:\.[0-9]+)+)\s+([\s\S]*?)(?=^Clause\s+[0-9]+(?:\.[0-9]+)+\s+|\Z)",
    re.MULTILINE,
)
_PERCENT = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*%")
_DAYS = re.compile(r"([0-9]+)\s*days?\b")


def _first_percent(text: str) -> float:
    match = _PERCENT.search(text or "")
    return float(match.group(1)) / 100.0 if match else 0.0


def _all_percents(text: str) -> List[float]:
    return [float(item) / 100.0 for item in _PERCENT.findall(text or "")]


def _first_days(text: str) -> int:
    match = _DAYS.search(text or "")
    return int(match.group(1)) if match else 0


def _parse_clauses(text: str) -> Dict[str, Dict[str, Any]]:
    """Read numbered clauses from the uploaded contract text itself."""
    clauses: Dict[str, Dict[str, Any]] = {}
    for number, body in _CLAUSE_LINE.findall(text or ""):
        body = " ".join(body.split())
        title, _, detail = body.partition(":")
        detail = detail or body
        entry: Dict[str, Any] = {
            "number": number,
            "title": title.strip(),
            "text": body,
        }
        percents = _all_percents(detail)
        if "time for completion" in title.lower():
            entry["days"] = _first_days(detail)
        elif "delay damages" in title.lower():
            entry["rate_per_day"] = percents[0] if percents else 0.0
            entry["cap_ratio"] = percents[1] if len(percents) > 1 else 0.0
        elif "defects notification" in title.lower():
            entry["days"] = _first_days(detail)
        elif "retention" in title.lower():
            entry["ratio"] = percents[0] if percents else 0.0
            releases = percents[1:] or []
            entry["release_at_taking_over"] = releases[0] if releases else 0.5
            entry["release_at_defects_end"] = releases[1] if len(releases) > 1 else 0.5
        elif "performance security" in title.lower():
            entry["ratio"] = _first_percent(detail)
        clauses[number] = entry
    return clauses


CLAUSES: Dict[str, Dict[str, Any]] = _parse_clauses(DOCUMENTS[CONTRACT_FILENAME])


def _number_for(title_fragment: str) -> str:
    wanted = str(title_fragment or "").strip().lower()
    for number, entry in CLAUSES.items():
        if str(entry.get("title") or "").lower() == wanted:
            return number
    for number, entry in CLAUSES.items():
        if wanted and wanted in str(entry.get("title") or "").lower():
            return number
    return ""


#: Clause identifiers as parsed from the uploaded contract -- never typed in.
TIME_FOR_COMPLETION = _number_for("time for completion")
DELAY_DAMAGES = _number_for("delay damages")
DEFECTS_NOTIFICATION = _number_for("defects notification period")
RETENTION = _number_for("retention")
PERFORMANCE_SECURITY = _number_for("performance security")


def clause(number: str) -> Dict[str, Any]:
    return dict(CLAUSES.get(str(number or "")) or {})


def clause_named(title_fragment: str) -> Dict[str, Any]:
    return clause(_number_for(title_fragment))


TIME_FOR_COMPLETION_DAYS = int(clause(TIME_FOR_COMPLETION).get("days") or 0)
DELAY_DAMAGES_RATE_PER_DAY = float(clause(DELAY_DAMAGES).get("rate_per_day") or 0.0)
DELAY_DAMAGES_CAP_RATIO = float(clause(DELAY_DAMAGES).get("cap_ratio") or 0.0)
RETENTION_RATIO = float(clause(RETENTION).get("ratio") or 0.0)
RETENTION_RELEASE_AT_TAKING_OVER = float(
    clause(RETENTION).get("release_at_taking_over") or 0.0
)
RETENTION_RELEASE_AT_DEFECTS_END = float(
    clause(RETENTION).get("release_at_defects_end") or 0.0
)
PERFORMANCE_SECURITY_RATIO = float(clause(PERFORMANCE_SECURITY).get("ratio") or 0.0)
DEFECTS_NOTIFICATION_DAYS = int(clause(DEFECTS_NOTIFICATION).get("days") or 0)


#: BOQ item : (description, unit, qty, rate) -- read from document:<BOQ_FILENAME>
def _parse_boq(text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    section = ""
    for raw in str(text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            section = line.lstrip("# ").strip()
            continue
        cells = [cell.strip() for cell in line.split("\t")]
        if len(cells) < 5 or cells[0].lower() == "item":
            continue
        try:
            quantity = float(cells[3])
            rate = float(cells[4])
        except ValueError:
            continue
        items.append(
            {
                "item": cells[0],
                "section": section,
                "description": cells[1],
                "unit": cells[2],
                "qty": int(quantity) if quantity.is_integer() else quantity,
                "rate": int(rate) if rate.is_integer() else rate,
            }
        )
    return items


BOQ_ITEMS: List[Dict[str, Any]] = _parse_boq(DOCUMENTS[BOQ_FILENAME])

#: The BOQ's own currency label, read from its "Rate (SAR)" column header.
_CURRENCY_HEADER = re.compile(r"Rate\s*\(([A-Z]{3})\)")


def _boq_currency() -> str:
    match = _CURRENCY_HEADER.search(DOCUMENTS[BOQ_FILENAME])
    return match.group(1) if match else ""


CURRENCY_LABEL = _boq_currency()


def currency_label() -> str:
    """The operator's declared currency, else the currency the BOQ states.

    A currency is never assumed: it is read from app.money_settings at the
    point of use, and only the source document's own label is the fallback.
    """
    from app import money_settings

    try:
        return money_settings.currency()
    except money_settings.MoneySettingMissing:
        return CURRENCY_LABEL


ACCEPTED_CONTRACT_AMOUNT = float(sum(item["qty"] * item["rate"] for item in BOQ_ITEMS))


def document_citation(filename: str) -> str:
    return "document:%s" % filename


def clause_citation(number: str) -> str:
    resolved = str(number or "")
    return "%s Clause %s" % (document_citation(CONTRACT_FILENAME), resolved) if resolved else document_citation(CONTRACT_FILENAME)


def boq_citation(item: str) -> str:
    return "%s item %s" % (document_citation(BOQ_FILENAME), item)


def boq_item(item_code: str) -> Dict[str, Any] | None:
    for item in BOQ_ITEMS:
        if item["item"] == str(item_code or "").strip().upper():
            return dict(item)
    return None


def corpus_text() -> str:
    """The source-of-record corpus the retrieval surface indexes."""
    return "\n\n".join(DOCUMENTS[filename] for filename in (CONTRACT_FILENAME, BOQ_FILENAME))
