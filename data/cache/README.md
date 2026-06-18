# Generated cache

This folder is populated by `scripts/build_openalex_cache.py` or by the GitHub Actions workflow.

The Streamlit app reads these parquet files. It should not scrape OpenAlex or push data to GitHub at page-load time.
