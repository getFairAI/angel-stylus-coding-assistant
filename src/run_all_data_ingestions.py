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


def main():
    parser = argparse.ArgumentParser(description="Run Stylus data ingestions")
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="Ignore previous ingestion_stats.json and refetch all sources",
    )
    args = parser.parse_args()

    write_ingestion_log("====================================")
    write_ingestion_log("Stylus ingestion pipeline started")
    write_ingestion_log("====================================")

    # Import inside main to avoid import-time crashes
    from ingestion.data_blog_ingestion import ingest_stylus_blog
    from ingestion.data_github_ingestion import ingest_github_readmes
    from ingestion.data_documentation_ingestion import ingest_stylus_docs
    from ingestion.data_github_issues_ingestion import ingest_github_issues
    from ingestion.data_stylus_framework_ingestion import ingest_stylus_framework
    from ingestion.data_awesome_stylus_code_ingestion import ingest_awesome_stylus_code
    from ingestion.data_stylus_versions_ingestion import ingest_stylus_versions
    from ingestion.data_stylus_course_ingestion import ingest_stylus_course
    from ingestion.data_openzeppelin_stylus_ingestion import ingest_openzeppelin_stylus_docs
    from fill_chroma import fill_chroma

    run_step("Stylus Blog", lambda: ingest_stylus_blog(force_refresh=args.force_refresh))
    run_step("GitHub READMEs", lambda: ingest_github_readmes(force_refresh=args.force_refresh))
    run_step("Github Issues & Comments", lambda: ingest_github_issues(force_refresh=args.force_refresh))
    run_step("Stylus Documentation", lambda: ingest_stylus_docs(force_refresh=args.force_refresh))
    run_step("LearnWeb3 Stylus Course", lambda: ingest_stylus_course(force_refresh=args.force_refresh))
    run_step("OZ Stylus Docs", lambda: ingest_openzeppelin_stylus_docs(force_refresh=args.force_refresh))
    run_step("Stylus Versions (changelog + PRs)", lambda: ingest_stylus_versions(force_refresh=args.force_refresh))
    run_step("Stylus Framework Code", lambda: ingest_stylus_framework(force_refresh=args.force_refresh))
    run_step("Awesome Stylus Community Code", lambda: ingest_awesome_stylus_code(force_refresh=args.force_refresh))
    run_step("Chroma Index Rebuild", fill_chroma)

    write_ingestion_log("====================================")
    write_ingestion_log("Stylus ingestion pipeline finished")
    write_ingestion_log("====================================")


if __name__ == "__main__":
    main()
