"""CLI entry point for running a pipeline from crontab.

Usage:
    python -m backend.scripts.pipeline_runner --pipeline-id 3

Exit code: 0 if the pipeline succeeded, 1 if it failed.
"""
import argparse
import sys


def main():
    parser = argparse.ArgumentParser(description="Run a ServerDash pipeline")
    parser.add_argument("--pipeline-id", type=int, required=True, help="ID of the pipeline to run")
    args = parser.parse_args()

    from backend.database import SessionLocal
    from backend.services.pipeline_service import run_pipeline

    db = SessionLocal()
    try:
        run = run_pipeline(args.pipeline_id, triggered_by="crontab", db=db)
        print(f"Pipeline {args.pipeline_id} finished: {run.status}")
        sys.exit(0 if run.status == "success" else 1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
