"""One-time migration: add performance indexes to execution_logs.

Run once against an existing database:
    python -m backend.scripts.add_indexes
"""
from sqlalchemy import text
from backend.database import engine


def main() -> None:
    statements = [
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_started_at ON execution_logs (started_at)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_username ON execution_logs (username)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_exit_code ON execution_logs (exit_code)",
        "CREATE INDEX IF NOT EXISTS ix_execution_logs_username_started_at ON execution_logs (username, started_at)",
        "CREATE INDEX IF NOT EXISTS ix_metrics_snapshots_timestamp ON metrics_snapshots (timestamp)",
    ]
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()
    print("Indexes applied.")


if __name__ == "__main__":
    main()
