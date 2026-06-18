from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from src.openalex_dashboard.config import (
    BASE_PAGE_TITLE,
    CACHE_DIR,
    DATASET_CONFIGS,
    DEFAULT_DATASET_KEY,
    get_dataset_display_order,
)
from src.openalex_dashboard.data import cache_status, load_bundle
from src.openalex_dashboard.filters import apply_global_filters, render_sidebar_filters
from src.openalex_dashboard.views.collaborators import render_collaborators_tab
from src.openalex_dashboard.views.data_quality import render_data_quality_tab
from src.openalex_dashboard.views.domains_sources import render_domains_sources_tab
from src.openalex_dashboard.views.explorer import render_explorer_tab
from src.openalex_dashboard.views.overview import render_overview_tab

st.set_page_config(page_title=BASE_PAGE_TITLE, page_icon="", layout="wide")

REQUIRED_WORK_SCHEMA_COLUMNS = ["keywords_json", "funders_json", "awards_json", "funder_names", "award_ids"]
REQUIRED_FEATURE_TABLES = ["keywords_long", "funding_long"]


def sync_browser_title(title: str) -> None:
    safe_title = title.replace("\\", "\\\\").replace("'", "\\'")
    components.html(
        f"""
        <script>
        window.parent.document.title = '{safe_title}';
        </script>
        """,
        height=0,
        width=0,
    )


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except Exception:
        return str(path)


def read_selected_dataset() -> str:
    params = st.query_params
    dataset_key = params.get("dataset", DEFAULT_DATASET_KEY)
    if isinstance(dataset_key, list):
        dataset_key = dataset_key[0]
    dataset_key = str(dataset_key).lower()
    if dataset_key not in DATASET_CONFIGS:
        dataset_key = DEFAULT_DATASET_KEY
    return dataset_key


def _dataset_nav_label(dataset_key: str) -> str:
    cfg = DATASET_CONFIGS[dataset_key]
    return cfg.get("navigation_label") or cfg.get("label", dataset_key)


def render_dataset_selector(current_dataset_key: str) -> str:
    dataset_options = get_dataset_display_order()
    if current_dataset_key not in dataset_options:
        current_dataset_key = DEFAULT_DATASET_KEY
    switch_col, _ = st.columns([1.25, 4], gap="small")
    with switch_col:
        selected_dataset_key = st.radio(
            "Organisation view",
            options=dataset_options,
            index=dataset_options.index(current_dataset_key),
            format_func=_dataset_nav_label,
            horizontal=False,
            label_visibility="visible",
        )
    if selected_dataset_key != current_dataset_key:
        st.query_params["dataset"] = selected_dataset_key
        st.rerun()
    return selected_dataset_key


def render_dataset_header(selected_cfg: dict) -> None:
    st.title(selected_cfg["title"])
    st.caption(selected_cfg["caption"])


def cache_needs_feature_schema_refresh(dataset_key: str) -> bool:
    status = cache_status(dataset_key)
    if not status["complete"]:
        return False
    works_path = status["required"].get("works")
    if not works_path or not Path(works_path).exists():
        return False
    try:
        import pyarrow.parquet as pq
        works_cols = set(pq.ParquetFile(works_path).schema.names)
    except Exception:
        try:
            works_cols = set(pd.read_parquet(works_path).columns)
        except Exception:
            return False
    missing_work_cols = [c for c in REQUIRED_WORK_SCHEMA_COLUMNS if c not in works_cols]
    missing_tables = [name for name in REQUIRED_FEATURE_TABLES if not status["optional"].get(name, Path()).exists()]
    return bool(missing_work_cols or missing_tables)


def render_cache_status_panel(dataset_key: str) -> None:
    status = cache_status(dataset_key)
    with st.sidebar:
        st.divider()
        with st.expander("Cache status", expanded=False):
            if status["complete"] and not cache_needs_feature_schema_refresh(dataset_key):
                st.success("Cache is present and has the topic/funding schema.")
            elif status["complete"]:
                st.warning("Cache is present but predates the topic/keyword/funding schema. Run the GitHub Action once.")
            else:
                st.error("Missing required cache: " + ", ".join(status["missing"]))
            st.caption(f"Cache folder: `{_display_path(CACHE_DIR)}`")
            st.caption("This deployed app only reads generated cache files. It does not scrape OpenAlex or push to GitHub during page loading.")


def render_missing_cache_instructions(dataset_key: str, error: Exception | None = None) -> None:
    cfg = DATASET_CONFIGS[dataset_key]
    st.error(f"No generated cache is available for {cfg['label']}.")
    if error:
        st.code(str(error))
    st.markdown(
        """
        The app is intentionally **read-only at page load**. Build the data first, then redeploy/read the committed cache.

        In GitHub:
        1. Open **Actions**.
        2. Open **Rebuild OpenAlex cache**.
        3. Click **Run workflow**.
        4. Wait until it commits generated parquet files under `data/cache/` and `data/outputs/`.
        5. Streamlit Community Cloud will relaunch from the updated repository.
        """
    )


def main() -> None:
    current_dataset_key = read_selected_dataset()
    selected_dataset_key = render_dataset_selector(current_dataset_key)
    selected_cfg = DATASET_CONFIGS[selected_dataset_key]
    sync_browser_title(selected_cfg["title"])
    render_dataset_header(selected_cfg)

    try:
        bundle = load_bundle(selected_dataset_key)
    except FileNotFoundError as exc:
        render_missing_cache_instructions(selected_dataset_key, exc)
        render_cache_status_panel(selected_dataset_key)
        st.stop()

    if cache_needs_feature_schema_refresh(selected_dataset_key):
        st.warning(
            "The loaded cache is older than this app version. The dashboard will still run, but topic/keyword/funding search may be incomplete. "
            "Run the GitHub Action once to rebuild the cache."
        )

    filters = render_sidebar_filters(bundle)
    render_cache_status_panel(selected_dataset_key)
    filtered = apply_global_filters(bundle, filters)

    tab_overview, tab_domains, tab_collab, tab_explorer, tab_quality = st.tabs(
        ["Overview", "Domains & Sources", "Collaborators", "Publications Explorer", "Data Quality"]
    )

    with tab_overview:
        render_overview_tab(bundle, filtered)
    with tab_domains:
        render_domains_sources_tab(bundle, filtered)
    with tab_collab:
        render_collaborators_tab(bundle, filtered)
    with tab_explorer:
        render_explorer_tab(bundle, filtered)
    with tab_quality:
        render_data_quality_tab(bundle, filtered)


if __name__ == "__main__":
    main()
