# OpenAlex Publications Dashboard

A cache-first Streamlit dashboard for exploring publications, collaborators, topics, sources and funding metadata for people linked to OpenAlex author IDs.

This version keeps the existing page structure and adds:

- a default year range starting from 2020 while preserving the full year slider;
- a global keyword search box that filters all pages;
- a topic/keyword selector based on cached OpenAlex topics and keywords;
- prioritised omics/platform/method terms in the selector when OpenAlex has them;
- funders and award/grant identifiers in the Publications Explorer;
- a GitHub Actions workflow that rebuilds generated data from raw staff CSVs and commits the cache back to the repository;
- a read-only Streamlit app at page load, so the public app does not scrape OpenAlex every time it starts.

## Repository layout

```text
.
├── app.py
├── requirements.txt
├── .github/workflows/rebuild-openalex-cache.yml
├── .streamlit/config.toml
├── data/
│   ├── raw/       # staff/person CSVs; source data
│   ├── cache/     # generated parquet cache; read by Streamlit
│   └── outputs/   # generated scraped publication CSVs
├── scripts/
│   ├── fetch_raw_data.py
│   └── build_openalex_cache.py
└── src/openalex_dashboard/
    ├── cache_builder.py
    ├── config.py
    ├── data.py
    ├── filters.py
    ├── matching.py
    ├── openalex_client.py
    └── views/
```

## Data workflow

The intended workflow is:

```text
raw staff CSVs in data/raw/
        ↓
GitHub Action or local script calls OpenAlex
        ↓
parquet cache written to data/cache/
        ↓
cache committed to GitHub
        ↓
Streamlit Community Cloud relaunches and only reads the cache
```

The app should **not** rebuild the cache from inside the Streamlit page. That would make public page loading slow, unstable, and hard to reproduce.

## Raw data files

Before generating data, place these files in `data/raw/`:

```text
data/raw/demography_openalex_people.csv
data/raw/ndph_openalex_people.csv
```

If you are starting from the previous public repository, the included workflow/script can fetch these two raw CSVs automatically from:

```text
https://raw.githubusercontent.com/midoriririta/subunit_tracking_dual_system_v3/main/data/raw/
```

For long-term reproducibility, it is better to commit the raw CSVs into the new public repo if they are not too large.

## Local build and test

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# optional: fetch raw CSVs from the original public repo
python scripts/fetch_raw_data.py

# build both NDPH and DSU caches
export OPENALEX_MAILTO="your.email@ox.ac.uk"
export OPENALEX_API_KEY="your_openalex_api_key"  # optional
python scripts/build_openalex_cache.py --dataset all

# launch locally
streamlit run app.py
```

Use `--dataset demography` or `--dataset ndph` to rebuild one view only.

## GitHub Action build

The workflow is in:

```text
.github/workflows/rebuild-openalex-cache.yml
```

It can be run manually from GitHub:

1. Open the new repository on GitHub.
2. Go to **Actions**.
3. Select **Rebuild OpenAlex cache**.
4. Click **Run workflow**.
5. Choose `all`, `demography`, or `ndph`.
6. Keep `fetch_raw_from_original_repo` enabled unless you already committed the raw CSVs.
7. Wait for the workflow to finish and push generated files under `data/cache/` and `data/outputs/`.

Add repository secrets first:

```text
OPENALEX_MAILTO = your.email@ox.ac.uk
OPENALEX_API_KEY = your OpenAlex API key, optional but recommended
```

The workflow has `permissions: contents: write` so it can commit generated data back to the repository.

## Deploy to Streamlit Community Cloud

1. Push this folder to a public GitHub repository.
2. Run the GitHub Action once so generated cache files exist.
3. Go to Streamlit Community Cloud.
4. Create a new app from your GitHub repo.
5. Set the main file path to:

```text
app.py
```

6. Add the same secrets in Streamlit if you want to use the cache builder locally from a private admin copy, although the deployed public app should only need the committed cache.
7. Deploy.

When the GitHub Action later commits fresh cache files, Streamlit should update/relaunch from the changed repo.

## GitHub file-size warning

The workflow checks for generated files above about 95 MB and fails before trying to commit them. GitHub blocks individual files above 100 MB and warns for large files. If any parquet file becomes too large, move generated cache to GitHub Releases, Hugging Face Dataset, S3, or another data host instead of committing it directly.

## What changed for topic/funding search

- `cache_builder.py` requests OpenAlex topics, keywords, funders and awards.
- `filters.py` builds a global sidebar topic/keyword selector and global search.
- `explorer.py` shows OpenAlex topics, keywords, funders and award IDs in the existing Publications Explorer.
- `app.py` starts with the 2020 view by default through the sidebar filter but preserves the full year range.
