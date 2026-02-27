# Ingestion Pipelines

This folder houses the fetch-and-prepare jobs that populate the RAG data JSON files and rebuild the Chroma collection.

## How to run everything

```bash
source .venv/bin/activate
python src/run_all_data_ingestions.py
```

- Writes progress to `logs/ingestion_logs.log`.
- Rebuilds Chroma at the end via `src/fill_chroma.py`, clearing and re-adding the `stylus_chat_data` collection.

## Pipelines at a glance

Each job saves JSON under `data/` (created on first run) and appends run details to the ingestion log.

| Script | What it ingests | Output file |
| --- | --- | --- |
| `data_blog_ingestion.py` | Stylus-tagged posts from blog.arbitrum.io | `data/stylus_blog.json` |
| `data_github_ingestion.py` | READMEs for core repos (`cargo-stylus`, `awesome-stylus`, `stylus-sdk-rs`) plus linked text assets from Awesome list | `data/github_readmes_sectioned.json` |
| `data_github_issues_ingestion.py` | Stylus GitHub issues and comments | `data/github_issues_sectioned.json` |
| `data_documentation_ingestion.py` | Official Arbitrum Stylus docs + by-example pages | `data/stylus_docs.json` |
| `data_openzeppelin_stylus_ingestion.py` | OpenZeppelin Contracts Stylus docs | `data/openzeppelin_stylus_docs.json` |
| `data_stylus_versions_ingestion.py` | `stylus-sdk-rs` changelog and recent merged PRs | `data/stylus_versions.json` |
| `data_stylus_course_ingestion.py` | LearnWeb3 Stylus course pages | `data/stylus_course.json` |
| `data_stylus_framework_ingestion.py` | Stylus framework code snippets | `data/stylus_framework_code.json` |
| `data_stylus_saturdays_ingestion.py` | Stylus Saturdays articles | `data/stylus_saturdays.json` |
| `data_awesome_stylus_code_ingestion.py` | Code files referenced from the Awesome Stylus list | `data/awesome_stylus_code.json` |

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

It deletes the existing `stylus_chat_data` collection in `./chroma_db` and re-adds chunked documents.

## Troubleshooting

- Check `logs/ingestion_logs.log` for failed URLs or rate-limit warnings.
- Missing `data/` directory is normal before the first run; scripts create it automatically.
- Oversized or non-text GitHub assets are skipped; see warnings in the log for context.
