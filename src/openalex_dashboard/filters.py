from __future__ import annotations

import re
from typing import Any, Dict

import pandas as pd

from src.openalex_dashboard.config import PRIORITY_TOPIC_TERMS

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    class _DummyStreamlit:
        def __getattr__(self, name):
            def _missing(*args, **kwargs):
                raise RuntimeError("Streamlit is required for UI rendering.")
            return _missing

    st = _DummyStreamlit()

CONFIDENCE_LEVELS = ["high", "medium", "low"]
DEFAULT_START_YEAR = 2020


def _normalise_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"high", "medium", "low"}:
        return text
    if text in {"med", "middle"}:
        return "medium"
    return "low" if text else "low"


def allowed_confidence_levels(include_medium: bool, include_low: bool) -> list[str]:
    levels = ["high"]
    if include_medium or include_low:
        levels.append("medium")
    if include_low:
        levels.append("low")
    return levels


def _lower_contains(series: pd.Series, text: str) -> pd.Series:
    if series is None or series.empty:
        return pd.Series(False, index=series.index if series is not None else [])
    return series.fillna("").astype(str).str.contains(re.escape(text), case=False, na=False)


def _topic_option_rows(bundle: Dict[str, Any], max_options: int = 140) -> pd.DataFrame:
    topics = bundle.get("topics_long", pd.DataFrame()).copy()
    keywords = bundle.get("keywords_long", pd.DataFrame()).copy()
    frames: list[pd.DataFrame] = []

    topic_specs = [
        ("topic", "topic_name"),
        ("subfield", "subfield_name"),
        ("field", "field_name"),
        ("domain", "domain_name"),
    ]
    if not topics.empty:
        for level, col in topic_specs:
            if col not in topics.columns:
                continue
            tmp = topics[["work_id", col]].dropna().copy()
            tmp[col] = tmp[col].astype(str).str.strip()
            tmp = tmp[tmp[col] != ""]
            if tmp.empty:
                continue
            grouped = (
                tmp.groupby(col, as_index=False)
                .agg(works_count=("work_id", "nunique"))
                .rename(columns={col: "value"})
            )
            grouped["level"] = level
            frames.append(grouped)

    if not keywords.empty and "keyword_name" in keywords.columns:
        tmp = keywords[["work_id", "keyword_name"]].dropna().copy()
        tmp["keyword_name"] = tmp["keyword_name"].astype(str).str.strip()
        tmp = tmp[tmp["keyword_name"] != ""]
        if not tmp.empty:
            grouped = (
                tmp.groupby("keyword_name", as_index=False)
                .agg(works_count=("work_id", "nunique"))
                .rename(columns={"keyword_name": "value"})
            )
            grouped["level"] = "keyword"
            frames.append(grouped)

    if not frames:
        return pd.DataFrame(columns=["option", "level", "value", "works_count", "priority"])

    options = pd.concat(frames, ignore_index=True).drop_duplicates(subset=["level", "value"])
    options["value_lower"] = options["value"].str.lower()
    options["priority"] = options["value_lower"].apply(
        lambda x: any(term.lower() in x for term in PRIORITY_TOPIC_TERMS)
    )
    options = options.sort_values(["priority", "works_count", "level", "value"], ascending=[False, False, True, True])
    options = options.head(max_options).copy()
    options["option"] = options.apply(
        lambda r: f"{str(r['level']).title()}: {r['value']} ({int(r['works_count'])})",
        axis=1,
    )
    return options[["option", "level", "value", "works_count", "priority"]]


def render_sidebar_filters(bundle: Dict[str, Any]) -> Dict[str, Any]:
    works = bundle["works"]
    authorships = bundle["authorships"]
    roster_works = bundle.get("roster_works", pd.DataFrame())
    people = bundle["people"]
    person_name_col = bundle.get("person_name_col")

    valid_years = works["publication_year"].dropna().astype(int) if "publication_year" in works.columns else []
    year_min = int(valid_years.min()) if len(valid_years) else 2000
    year_max = int(valid_years.max()) if len(valid_years) else 2026
    default_start = min(max(DEFAULT_START_YEAR, year_min), year_max)

    roster_options: list[str] = []
    if not roster_works.empty and "staff_name" in roster_works.columns:
        roster_options = sorted(roster_works["staff_name"].dropna().astype(str).unique().tolist())
    elif "roster_person_name" in authorships.columns:
        roster_options = sorted(
            authorships.loc[authorships["roster_person_name"].notna(), "roster_person_name"].astype(str).unique().tolist()
        )
    elif person_name_col:
        roster_options = sorted(people.loc[people[person_name_col].notna(), person_name_col].astype(str).unique().tolist())

    source_type_options: list[str] = []
    if "source_type" in works.columns:
        source_type_options = sorted(works["source_type"].dropna().astype(str).unique().tolist())

    topic_options_df = _topic_option_rows(bundle)
    topic_option_labels = topic_options_df["option"].tolist() if not topic_options_df.empty else []
    topic_option_records = topic_options_df.set_index("option").to_dict("index") if not topic_options_df.empty else {}

    with st.sidebar:
        st.header("Filters")
        year_range = st.slider(
            "Publication year range",
            min_value=year_min,
            max_value=year_max,
            value=(default_start, year_max),
            help="Default view starts at 2020, but the full year range remains available.",
        )

        selected_people = st.multiselect("Selected people", options=roster_options, default=[])
        selected_source_types = st.multiselect("Source type", options=source_type_options, default=source_type_options)
        oa_only = st.checkbox("Open access only", value=False)
        min_citations = st.number_input("Minimum cited_by_count", min_value=0, value=0, step=1)

        st.markdown("**Topic / keyword search**")
        search_text = st.text_input(
            "Search papers, topics, keywords, authors or funders",
            value="",
            placeholder="e.g. proteomics, OLINK, genomics, mass spectrometry, Rahal",
            help="Searches cached titles, sources, OpenAlex topics/keywords, authors/staff, funders and award IDs.",
        )
        selected_topic_options = st.multiselect(
            "Select OpenAlex topics / keywords",
            options=topic_option_labels,
            default=[],
            help=(
                "Priority omics/platform terms are shown first when they exist in the cached OpenAlex topics/keywords; "
                "otherwise the list falls back to common OpenAlex topics, subfields, fields and domains."
            ),
        )

        st.markdown("**Publication confidence**")
        include_medium = st.checkbox(
            "Enable medium confidence papers",
            value=False,
            help="Default is high-confidence papers only. Medium keeps papers with a credible author match but weaker paper-level evidence.",
        )
        include_low = st.checkbox(
            "Enable medium and low confidence papers",
            value=False,
            help="Use this for auditing or manual review. It is intentionally off by default.",
        )

    if include_low and not include_medium:
        include_medium = True

    return {
        "year_range": year_range,
        "selected_people": selected_people,
        "selected_source_types": selected_source_types,
        "oa_only": oa_only,
        "min_citations": min_citations,
        "search_text": search_text.strip(),
        "selected_topic_options": selected_topic_options,
        "topic_option_records": topic_option_records,
        "confidence_levels": allowed_confidence_levels(include_medium, include_low),
    }


def _work_ids_matching_topic_options(
    topics_long: pd.DataFrame,
    keywords_long: pd.DataFrame,
    selected_topic_options: list[str],
    option_records: dict[str, dict[str, Any]],
) -> set[str]:
    if not selected_topic_options:
        return set()

    keep: set[str] = set()
    col_by_level = {
        "topic": "topic_name",
        "subfield": "subfield_name",
        "field": "field_name",
        "domain": "domain_name",
    }
    for option in selected_topic_options:
        rec = option_records.get(option, {})
        level = rec.get("level")
        value = str(rec.get("value") or "")
        if not value:
            continue
        if level == "keyword":
            if not keywords_long.empty and "keyword_name" in keywords_long.columns:
                ids = keywords_long.loc[keywords_long["keyword_name"].astype(str) == value, "work_id"].dropna().astype(str)
                keep.update(ids.tolist())
        else:
            col = col_by_level.get(str(level))
            if col and not topics_long.empty and col in topics_long.columns:
                ids = topics_long.loc[topics_long[col].astype(str) == value, "work_id"].dropna().astype(str)
                keep.update(ids.tolist())
    return keep


def _work_ids_matching_text(
    works: pd.DataFrame,
    authorships: pd.DataFrame,
    topics_long: pd.DataFrame,
    keywords_long: pd.DataFrame,
    funding_long: pd.DataFrame,
    roster_works: pd.DataFrame,
    text: str,
) -> set[str]:
    if not text:
        return set()

    keep: set[str] = set()
    work_cols = [
        "title",
        "source_name",
        "doi",
        "work_id",
        "funder_names",
        "award_ids",
        "source_type",
        "work_type",
    ]
    for col in work_cols:
        if col in works.columns:
            keep.update(works.loc[_lower_contains(works[col], text), "work_id"].dropna().astype(str).tolist())

    if not authorships.empty and "work_id" in authorships.columns:
        for col in ["author_name", "raw_author_name", "roster_person_name"]:
            if col in authorships.columns:
                keep.update(authorships.loc[_lower_contains(authorships[col], text), "work_id"].dropna().astype(str).tolist())

    if not roster_works.empty and "work_id" in roster_works.columns:
        for col in ["staff_name", "author_display_name", "raw_author_name", "title"]:
            if col in roster_works.columns:
                keep.update(roster_works.loc[_lower_contains(roster_works[col], text), "work_id"].dropna().astype(str).tolist())

    if not topics_long.empty and "work_id" in topics_long.columns:
        for col in ["topic_name", "subfield_name", "field_name", "domain_name"]:
            if col in topics_long.columns:
                keep.update(topics_long.loc[_lower_contains(topics_long[col], text), "work_id"].dropna().astype(str).tolist())

    if not keywords_long.empty and "work_id" in keywords_long.columns:
        for col in ["keyword_name"]:
            if col in keywords_long.columns:
                keep.update(keywords_long.loc[_lower_contains(keywords_long[col], text), "work_id"].dropna().astype(str).tolist())

    if not funding_long.empty and "work_id" in funding_long.columns:
        for col in ["funder_name", "award_id", "award_openalex_id", "funder_id"]:
            if col in funding_long.columns:
                keep.update(funding_long.loc[_lower_contains(funding_long[col], text), "work_id"].dropna().astype(str).tolist())

    return keep


def apply_global_filters(bundle: Dict[str, Any], filters: Dict[str, Any]) -> Dict[str, Any]:
    works = bundle["works"].copy()
    authorships = bundle["authorships"].copy()
    topics_long = bundle["topics_long"].copy()
    keywords_long = bundle.get("keywords_long", pd.DataFrame()).copy()
    funding_long = bundle.get("funding_long", pd.DataFrame()).copy()
    roster_works = bundle.get("roster_works", pd.DataFrame()).copy()

    year_start, year_end = filters["year_range"]
    if "publication_year" in works.columns:
        works = works[works["publication_year"].fillna(-999999).between(year_start, year_end)]

    selected_source_types = filters["selected_source_types"]
    if selected_source_types and "source_type" in works.columns:
        works = works[works["source_type"].isin(selected_source_types)]

    if filters["oa_only"] and "is_oa" in works.columns:
        works = works[works["is_oa"] == True]

    if "cited_by_count" in works.columns:
        works = works[works["cited_by_count"].fillna(0) >= filters["min_citations"]]

    selected_people = filters["selected_people"]
    if selected_people:
        if not roster_works.empty and "staff_name" in roster_works.columns:
            keep_work_ids = roster_works.loc[roster_works["staff_name"].isin(selected_people), "work_id"].dropna().unique()
            works = works[works["work_id"].isin(keep_work_ids)]
        elif "roster_person_name" in authorships.columns:
            keep_work_ids = authorships.loc[authorships["roster_person_name"].isin(selected_people), "work_id"].dropna().unique()
            works = works[works["work_id"].isin(keep_work_ids)]

    keep_work_ids = set(works["work_id"].dropna().astype(str).tolist()) if "work_id" in works.columns else set()

    selected_topic_options = filters.get("selected_topic_options", [])
    if selected_topic_options:
        topic_ids = _work_ids_matching_topic_options(
            topics_long=topics_long,
            keywords_long=keywords_long,
            selected_topic_options=selected_topic_options,
            option_records=filters.get("topic_option_records", {}),
        )
        keep_work_ids &= topic_ids
        works = works[works["work_id"].astype(str).isin(keep_work_ids)]

    search_text = filters.get("search_text", "")
    if search_text:
        text_ids = _work_ids_matching_text(
            works=works,
            authorships=authorships,
            topics_long=topics_long,
            keywords_long=keywords_long,
            funding_long=funding_long,
            roster_works=roster_works,
            text=search_text,
        )
        keep_work_ids &= text_ids
        works = works[works["work_id"].astype(str).isin(keep_work_ids)]

    keep_work_ids = set(works["work_id"].dropna().astype(str).tolist()) if "work_id" in works.columns else set()

    if not roster_works.empty and "work_id" in roster_works.columns:
        roster_works = roster_works[roster_works["work_id"].astype(str).isin(keep_work_ids)].copy()
        if "paper_confidence" in roster_works.columns:
            roster_works["paper_confidence_norm"] = roster_works["paper_confidence"].map(_normalise_confidence)
            roster_works = roster_works[roster_works["paper_confidence_norm"].isin(filters["confidence_levels"])]
            keep_work_ids = set(roster_works["work_id"].dropna().astype(str).tolist())
            works = works[works["work_id"].astype(str).isin(keep_work_ids)]

    if "work_id" in authorships.columns:
        authorships = authorships[authorships["work_id"].astype(str).isin(keep_work_ids)].copy()
    if "work_id" in topics_long.columns:
        topics_long = topics_long[topics_long["work_id"].astype(str).isin(keep_work_ids)].copy()
    if not keywords_long.empty and "work_id" in keywords_long.columns:
        keywords_long = keywords_long[keywords_long["work_id"].astype(str).isin(keep_work_ids)].copy()
    if not funding_long.empty and "work_id" in funding_long.columns:
        funding_long = funding_long[funding_long["work_id"].astype(str).isin(keep_work_ids)].copy()

    return {
        "works": works,
        "authorships": authorships,
        "topics_long": topics_long,
        "keywords_long": keywords_long,
        "funding_long": funding_long,
        "roster_works": roster_works,
    }
