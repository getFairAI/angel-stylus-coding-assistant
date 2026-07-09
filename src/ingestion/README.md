# Ingestion Pipelines

This folder houses the fetch-and-prepare jobs that populate the RAG data JSON files and rebuild the Chroma collection.

## How to run everything

```bash
source .venv/bin/activate
python src/run_all_data_ingestions.py
```

In Docker this runs automatically: the `ingestion` service (`src/ingestion_scheduler.py`)
executes the pipeline on start and then every `INGEST_INTERVAL_SECONDS`, writing to the shared
Chroma server. No systemd timer/cron needed. Trigger an extra run with
`docker compose exec ingestion python src/run_all_data_ingestions.py`.

- Writes progress to `logs/ingestion_logs.log`.
- Refreshes Chroma at the end via `src/fill_chroma.py`. Chunk ids are content-derived, so it
  **upserts only new/changed chunks and deletes removed ones** — the `stylus_chat_data` collection
  is never emptied and the live API keeps serving during a rebuild.

## Pipelines at a glance

Each job saves JSON under `data/` (created on first run) and appends run details to the ingestion log.

| Script | What it ingests | Output file |
| --- | --- | --- |
| `data_blog_ingestion.py` | Stylus-tagged posts from blog.arbitrum.io | `data/stylus_blog.json` |
| `data_github_ingestion.py` | READMEs for core repos (`cargo-stylus`, `awesome-stylus`, `stylus-sdk-rs`) plus linked text assets from Awesome list | `data/github_readmes_sectioned.json` |
| `data_github_issues_ingestion.py` | Stylus GitHub issues and comments | `data/github_issues_sectioned.json` |
| `data_documentation_ingestion.py` | Official Arbitrum Stylus docs + by-example pages | `data/stylus_docs.json` |
| `data_openzeppelin_stylus_ingestion.py` | OpenZeppelin Contracts Stylus docs | `data/openzeppelin_stylus_docs.json` |
| `data_openzeppelin_stylus_code_ingestion.py` | OpenZeppelin `rust-contracts-stylus` contract source (release-pinned) | `data/openzeppelin_stylus_code.json` |
| `data_stylus_versions_ingestion.py` | `stylus-sdk-rs` changelog and recent merged PRs | `data/stylus_versions.json` |
| `data_stylus_course_ingestion.py` | LearnWeb3 Stylus course pages | `data/stylus_course.json` |
| `data_stylus_framework_ingestion.py` | `stylus-sdk-rs` source, last 3 minor releases side-by-side | `data/stylus_framework_code.json` |
| `data_stylus_by_example_ingestion.py` | Stylus-by-Example repo source (examples + walkthroughs) | `data/stylus_by_example_code.json` |
| `data_stylus_saturdays_ingestion.py` | Stylus Saturdays articles | `data/stylus_saturdays.json` |
| `data_awesome_stylus_code_ingestion.py` | Quality-filtered code from repos in the Awesome Stylus list | `data/awesome_stylus_code.json` |
| `data_stylus_saturdays_ingestion.py` | Stylus Saturdays articles (requires `playwright`) | `data/stylus_saturdays.json` |

## SDK version awareness

Code sources are version-anchored so retrieval can distinguish SDK versions and
avoid surfacing deprecated APIs as current (see `code_repo_utils.py`):

- The **SDK framework** job keeps the newest patch of each of the last
  `STYLUS_SDK_KEEP_MINORS` (default 3) minor releases side-by-side — each chunk
  stamped with its own `sdk_version`, so version-specific questions get
  version-appropriate code. Releases that roll off the window are pruned.
- The **OpenZeppelin contracts** job pins to the repo's latest **release tag**
  (not moving HEAD) and stamps `metadata.sdk_version` + `released_at`.
- **Community code** (`awesome_stylus_code`) parses each repo's `Cargo.toml`
  `stylus-sdk` dependency and stamps `sdk_version`. Repos are quality-filtered:
  archived repos are dropped, along with those below `AWESOME_MIN_STARS`
  (default 2) or not pushed within `AWESOME_MAX_AGE_DAYS` (default 730); every
  drop is logged. Only `.rs`/`.toml`/`.md` are ingested.
- At query time (`retrieve_chroma_docs.py`) `sdk_version` is surfaced in the
  context header and citations, and code-intent ranking prefers version-anchored
  chunks while down-ranking pre-0.6 (and hard-skipping pre-0.4) API-era code.

## Incremental behavior

- Most jobs load existing JSON via `incremental_utils.load_entries` and merge new/changed records with `merge_entries`, preserving unchanged items and retaining previously ingested records when a source is temporarily unreachable.
- Each entry carries `metadata.ingested_at`; GitHub-oriented jobs also store repo-specific keys for stable merge keys.

## Environment and rate limits

- Outbound HTTP is required (GitHub, Arbitrum docs/blog, OpenZeppelin docs).
- For GitHub-heavy jobs (`data_github_*`, `data_stylus_versions_ingestion.py`, `data_awesome_stylus_code_ingestion.py`), set `GITHUB_TOKEN` to increase rate limits:

```bash
export GITHUB_TOKEN=ghp_xxx
```

## Rebuilding Chroma only

If data JSON already exists and you just want to refresh the vector store:

```bash
python src/fill_chroma.py
```

It reconciles the `stylus_chat_data` collection in `./chroma_db` against `data/`: chunks are split
(`CHUNK_MAX_CHARS`/`CHUNK_OVERLAP`), assigned content-derived ids, and **upserted** — only new/changed
chunks are embedded, stale ids are deleted, and unchanged chunks are left untouched. Requires the
ollama embeddings backend (`OLLAMA_HOST` / `EMBEDDING_MODEL`).

The Stylus Saturdays job additionally needs `playwright` (`pip install playwright && playwright
install chromium`); it is wired into the orchestrator but a missing dependency fails only that step.

## Troubleshooting

- Check `logs/ingestion_logs.log` for failed URLs or rate-limit warnings.
- Missing `data/` directory is normal before the first run; scripts create it automatically.
- Oversized or non-text GitHub assets are skipped; see warnings in the log for context.
