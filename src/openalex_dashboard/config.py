from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
CACHE_DIR = DATA_DIR / "cache"
OUTPUT_DIR = DATA_DIR / "outputs"

BASE_PAGE_TITLE = "Department Publications Dashboard"
PAGE_TITLE = BASE_PAGE_TITLE

OPENALEX_MAILTO_ENV = "OPENALEX_MAILTO"
OPENALEX_API_KEY_ENV = "OPENALEX_API_KEY"
DEFAULT_OPENALEX_MAILTO = os.environ.get(OPENALEX_MAILTO_ENV, "").strip()

DATASET_CONFIGS = {
    "demography": {
        "key": "demography",
        "label": "Demographic Science Unit",
        "navigation_label": "    ↳ Demographic Science Unit",
        "parent_key": "ndph",
        "parent_label": "NDPH Department",
        "hierarchy_level": 1,
        "display_order": 20,
        "suffix": "",
        "title": "Demographic Science Unit Publications Dashboard",
        "caption": (
            "Dashboard using OpenAlex data for people in the Demographic Science Unit, "
            "shown as a subunit of the Nuffield Department of Population Health."
        ),
        "default_staff_csv": RAW_DIR / "demography_openalex_people.csv",
        "legacy_staff_csv": RAW_DIR / "demography_openalex_people.csv",
    },
    "ndph": {
        "key": "ndph",
        "label": "NDPH Department",
        "navigation_label": "NDPH Department",
        "parent_key": None,
        "parent_label": None,
        "hierarchy_level": 0,
        "display_order": 10,
        "suffix": "_ndph",
        "title": "NDPH Department Publications Dashboard",
        "caption": "Dashboard using OpenAlex data for people in the Nuffield Department of Population Health.",
        "default_staff_csv": RAW_DIR / "ndph_openalex_people.csv",
        "legacy_staff_csv": RAW_DIR / "ndph_openalex_people.csv",
    },
}

DEFAULT_DATASET_KEY = "demography"

REQUIRED_CACHE_TABLES = ["people", "works", "authorships", "institutions", "topics_long"]
OPTIONAL_CACHE_TABLES = ["author_candidates", "roster_works", "keywords_long", "funding_long"]

REQUIRED_AGGREGATES = [
    "agg_publications_by_year",
    "agg_citations_by_pubyear",
    "agg_collaborator_countries_by_year",
    "agg_domains_by_year",
    "agg_sources_by_year",
    "agg_confidence_by_year",
]

OXFORD_TERMS = [
    "university of oxford",
    "oxford university",
    "department of population health",
    "nuffield department of population health",
    "ndph",
    "demographic science unit",
    "demography",
    "leverhulme centre for demographic science",
    "lcds",
]

# These terms do not label papers directly. They only prioritise cached OpenAlex
# topic/keyword options so the selector exposes biologically useful choices first.
PRIORITY_TOPIC_TERMS = [
    "proteomics",
    "metabolomics",
    "lipidomics",
    "genetics",
    "genomics",
    "multiplex",
    "immunoassay",
    "immunoassays",
    "olink",
    "somalogic",
    "somascan",
    "illumina",
    "alamar",
    "metabolon",
    "nightingale",
    "biocrates",
    "affymetrix",
    "mass spectrometry",
    "nmr",
    "nuclear magnetic resonance",
    "transcriptomics",
    "biomarker",
    "biomarkers",
    "epigenomics",
    "phenomics",
    "microbiome",
    "single-cell",
    "single cell",
]


def get_dataset_config(dataset_key: str | None) -> dict:
    dataset_key = (dataset_key or DEFAULT_DATASET_KEY).lower()
    return DATASET_CONFIGS.get(dataset_key, DATASET_CONFIGS[DEFAULT_DATASET_KEY]).copy()


def get_dataset_display_order() -> list[str]:
    return sorted(
        DATASET_CONFIGS.keys(),
        key=lambda key: (
            DATASET_CONFIGS[key].get("display_order", 999),
            DATASET_CONFIGS[key].get("hierarchy_level", 0),
            DATASET_CONFIGS[key].get("label", key),
        ),
    )
