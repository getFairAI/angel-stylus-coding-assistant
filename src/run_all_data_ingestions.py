import argparse
import traceback
from datetime import datetime

from basic_logs import write_ingestion_log


def run_step(name, fn):
    write_ingestion_log(f"START | {name}")
    print(f"\n=== Running: {name} ===")

    start = datetime.utcnow()

    try:
        fn()
        duration = (datetime.utcnow() - start).total_seconds()
        write_ingestion_log(f"OK | {name} finished in {duration:.1f}s")
        print(f"[ok] {name} finished in {duration:.1f}s")

    except Exception as e:
        write_ingestion_log(f"ERROR | {name} failed: {e}")
        print(f"[error] {name} failed: {e}")
        traceback.print_exc()


def run_all(force_refresh: bool = False):
    """Run every ingestion job in order, then rebuild the Chroma index.

    Each job is imported and executed inside its own ``run_step`` so an import
    failure (e.g. an optional dependency like playwright for the course/Saturdays
    scrapers) fails only that step instead of aborting the whole pipeline.
    Exposed as a callable so the scheduler (and tests) can invoke it directly
    without going through argparse.
    """
    import importlib

    write_ingestion_log("====================================")
    write_ingestion_log("Stylus ingestion pipeline started")
    write_ingestion_log("====================================")

    # (step label, module, callable) — every job takes force_refresh.
    jobs = [
        ("Stylus Blog", "ingestion.data_blog_ingestion", "ingest_stylus_blog"),
        ("GitHub READMEs", "ingestion.data_github_ingestion", "ingest_github_readmes"),
        ("Github Issues & Comments", "ingestion.data_github_issues_ingestion", "ingest_github_issues"),
        ("Stylus Documentation", "ingestion.data_documentation_ingestion", "ingest_stylus_docs"),
        ("LearnWeb3 Stylus Course", "ingestion.data_stylus_course_ingestion", "ingest_stylus_course"),
        ("OZ Stylus Docs", "ingestion.data_openzeppelin_stylus_ingestion", "ingest_openzeppelin_stylus_docs"),
        ("Stylus Versions (changelog + PRs)", "ingestion.data_stylus_versions_ingestion", "ingest_stylus_versions"),
        ("Stylus Framework Code", "ingestion.data_stylus_framework_ingestion", "ingest_stylus_framework"),
        ("Stylus By Example Code", "ingestion.data_stylus_by_example_ingestion", "ingest_stylus_by_example"),
        ("OZ Stylus Contracts Code", "ingestion.data_openzeppelin_stylus_code_ingestion", "ingest_openzeppelin_stylus_code"),
        ("Awesome Stylus Community Code", "ingestion.data_awesome_stylus_code_ingestion", "ingest_awesome_stylus_code"),
        ("Stylus Saturdays", "ingestion.data_stylus_saturdays_ingestion", "scrape_all"),
    ]

    def make_step(module_path: str, fn_name: str):
        # Import lazily at call time so a missing optional dependency only fails
        # this step, not the whole run_all import.
        def run():
            module = importlib.import_module(module_path)
            getattr(module, fn_name)(force_refresh=force_refresh)
        return run

    for label, module_path, fn_name in jobs:
        run_step(label, make_step(module_path, fn_name))

    from fill_chroma import fill_chroma
    run_step("Chroma Index Rebuild", fill_chroma)

    write_ingestion_log("====================================")
    write_ingestion_log("Stylus ingestion pipeline finished")
    write_ingestion_log("====================================")


def main():
    parser = argparse.ArgumentParser(description="Run Stylus data ingestions")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore previous ingestion_stats.json and refetch all sources",
    )
    args = parser.parse_args()
    run_all(force_refresh=args.force_refresh)


if __name__ == "__main__":
    main()
