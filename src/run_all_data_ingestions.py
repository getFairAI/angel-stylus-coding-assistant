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
    write_ingestion_log("====================================")
    write_ingestion_log("Stylus ingestion pipeline started")
    write_ingestion_log("====================================")


    # Import inside main to avoid import-time crashes
    from data_blog_ingestion import ingest_stylus_blog
    from data_github_ingestion import ingest_github_readmes
    from data_documentation_ingestion import ingest_stylus_docs

    run_step("Stylus Blog", ingest_stylus_blog)
    run_step("GitHub READMEs", ingest_github_readmes)
    run_step("Stylus Documentation", ingest_stylus_docs)

    write_ingestion_log("====================================")
    write_ingestion_log("Stylus ingestion pipeline finished")
    write_ingestion_log("====================================")



if __name__ == "__main__":
    main()
