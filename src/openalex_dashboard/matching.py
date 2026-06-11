from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import pandas as pd

from src.openalex_dashboard.config import OXFORD_TERMS


@dataclass
class AuthorMatch:
    staff_index: int
    staff_name: str
    openalex_author_id_short: str
    openalex_author_id_full: str
    author_display_name: str
    score: float
    confidence: str
    reasons: list[str]
    record: dict[str, Any]


def safe_json(value: Any) -> str:
    try:
        return json.dumps(value if value is not None else [], ensure_ascii=False)
    except Exception:
        return "[]"


def normalise_openalex_author_id(value: Any) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "null"}:
        return None
    text = text.rstrip("/")
    if "/" in text:
        text = text.split("/")[-1]
    text = text.upper()
    return text if re.fullmatch(r"A\d+", text) else None


def _first_existing(row: Any, candidates: list[str]) -> Any:
    for candidate in candidates:
        if candidate in row and pd.notna(row[candidate]):
            value = row[candidate]
            if str(value).strip() and str(value).strip().lower() != "nan":
                return value
    return None


def _normalise_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def extract_staff_fields(row: Any) -> dict[str, Any]:
    """Extract a robust staff/person record from slightly different CSV schemas."""
    if hasattr(row, "to_dict"):
        row_dict = row.to_dict()
    else:
        row_dict = dict(row)
    lower_to_original = {str(k).lower().strip(): k for k in row_dict.keys()}

    def get(*names: str) -> Any:
        for name in names:
            key = lower_to_original.get(name.lower())
            if key is not None:
                value = row_dict.get(key)
                if value is not None and not (isinstance(value, float) and pd.isna(value)):
                    text = str(value).strip()
                    if text and text.lower() != "nan":
                        return value
        return None

    return {
        "name": get("name", "full_name", "person_name", "staff_name", "display_name", "author_display_name"),
        "email": get("email", "mail", "primary_email"),
        "orcid": get("orcid", "openalex_orcid"),
        "openalex_author_id": get("openalex_author_id", "author_id", "author_openalex_id", "openalex_id"),
        "role": get("role", "job_title", "title"),
        "profile_url": get("profile_url", "url", "webpage"),
        "department": get("department", "dept", "unit"),
        "subunit": get("subunit", "group", "team"),
        "primary_institution": get("primary_institution", "institution", "organisation", "organization"),
        "recent_publications_json": get("recent_publications_json", "recent_publications", "publications_json"),
        "start_year": get("start_year"),
        "end_year": get("end_year"),
    }


def _name_similarity(a: Any, b: Any) -> float:
    a_norm = _normalise_text(a)
    b_norm = _normalise_text(b)
    if not a_norm or not b_norm:
        return 0.0
    return SequenceMatcher(None, a_norm, b_norm).ratio()


def _author_in_oxford_context(author_record: dict[str, Any]) -> bool:
    chunks: list[str] = []
    for inst in author_record.get("last_known_institutions") or []:
        chunks.append(str(inst.get("display_name") or ""))
    for aff in author_record.get("affiliations") or []:
        inst = aff.get("institution") or {}
        chunks.append(str(inst.get("display_name") or ""))
    text = _normalise_text(" ".join(chunks))
    return any(term in text for term in OXFORD_TERMS)


def score_author_candidate(staff: dict[str, Any], author_record: dict[str, Any], explicit_id: bool = False) -> tuple[float, str, list[str]]:
    reasons: list[str] = []
    score = 0.0

    staff_name = staff.get("name") or ""
    author_name = author_record.get("display_name") or ""
    name_score = _name_similarity(staff_name, author_name)
    score += 0.45 * name_score
    reasons.append(f"name similarity={name_score:.2f}")

    staff_orcid = _normalise_text(staff.get("orcid"))
    author_orcid = _normalise_text((author_record.get("ids") or {}).get("orcid"))
    if staff_orcid and author_orcid and staff_orcid == author_orcid:
        score += 0.35
        reasons.append("ORCID match")

    if explicit_id:
        score += 0.35
        reasons.append("explicit OpenAlex author ID")

    if _author_in_oxford_context(author_record):
        score += 0.15
        reasons.append("Oxford/NDPH institutional context")

    works_count = author_record.get("works_count") or 0
    if works_count:
        score += min(float(works_count), 100.0) / 1000.0
        reasons.append(f"works_count={works_count}")

    score = max(0.0, min(score, 1.0))
    if explicit_id or score >= 0.78:
        confidence = "high"
    elif score >= 0.55:
        confidence = "medium"
    else:
        confidence = "low"
    return score, confidence, reasons


def _recent_titles(staff: dict[str, Any]) -> list[str]:
    raw = staff.get("recent_publications_json")
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return []
    try:
        pubs = json.loads(raw) if isinstance(raw, str) else raw
    except Exception:
        return []
    if not isinstance(pubs, list):
        return []
    out: list[str] = []
    for item in pubs:
        if isinstance(item, dict) and item.get("title"):
            out.append(str(item["title"]))
    return out


def score_work_for_staff(
    staff: dict[str, Any],
    author_match_score: float,
    author_match_confidence: str,
    work: dict[str, Any],
    authorship: dict[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    score = 0.0

    if author_match_confidence == "high":
        score += 0.55
        reasons.append("high author match")
    elif author_match_confidence == "medium":
        score += 0.38
        reasons.append("medium author match")
    else:
        score += 0.18
        reasons.append("low author match")

    score += min(max(author_match_score, 0.0), 1.0) * 0.20

    raw_author_name = authorship.get("raw_author_name") or (authorship.get("author") or {}).get("display_name")
    if _name_similarity(staff.get("name"), raw_author_name) >= 0.82:
        score += 0.12
        reasons.append("author-name appears on work")

    title = work.get("display_name") or ""
    title_match = 0.0
    for recent in _recent_titles(staff):
        title_match = max(title_match, _name_similarity(title, recent))
    if title_match >= 0.80:
        score += 0.20
        reasons.append("matches recent publication in staff profile")

    inst_text = _normalise_text(" ".join(authorship.get("raw_affiliation_strings") or []))
    for inst in authorship.get("institutions") or []:
        inst_text += " " + _normalise_text(inst.get("display_name"))
    if any(term in inst_text for term in OXFORD_TERMS):
        score += 0.08
        reasons.append("Oxford/NDPH affiliation on authorship")

    score = max(0.0, min(score, 1.0))
    if score >= 0.70:
        confidence = "high"
    elif score >= 0.45:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "paper_confidence_score": round(score, 4),
        "paper_confidence": confidence,
        "paper_confidence_reasons": "; ".join(reasons),
    }
