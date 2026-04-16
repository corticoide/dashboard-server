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
        "CREATE INDEX IF NOT EXISTS ix_permissions_role ON permissions (role)",
        "CREATE INDEX IF NOT EXISTS ix_permissions_role_resource ON permissions (role, resource)",
        "CREATE INDEX IF NOT EXISTS ix_network_snapshots_timestamp ON network_snapshots (timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_network_snapshots_interface ON network_snapshots (interface)",
        "CREATE INDEX IF NOT EXISTS ix_network_snapshots_interface_timestamp ON network_snapshots (interface, timestamp)",
        "CREATE INDEX IF NOT EXISTS ix_pipeline_steps_pipeline_id ON pipeline_steps (pipeline_id)",
        "CREATE INDEX IF NOT EXISTS ix_pipeline_runs_pipeline_id  ON pipeline_runs  (pipeline_id)",
        "CREATE INDEX IF NOT EXISTS ix_pipeline_runs_started_at   ON pipeline_runs  (started_at)",
        "CREATE INDEX IF NOT EXISTS ix_pipeline_step_runs_run_id  ON pipeline_step_runs (run_id)",
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_enabled ON alert_rules (enabled)",
        "CREATE INDEX IF NOT EXISTS ix_alert_rules_condition_type ON alert_rules (condition_type)",
        "CREATE INDEX IF NOT EXISTS ix_alert_fires_rule_id ON alert_fires (rule_id)",
        "CREATE INDEX IF NOT EXISTS ix_alert_fires_status ON alert_fires (status)",
        "CREATE INDEX IF NOT EXISTS ix_alert_fires_fired_at ON alert_fires (fired_at)",
    ]
    with engine.connect() as conn:
        for stmt in statements:
            conn.execute(text(stmt))
        conn.commit()
    print("Indexes applied.")


if __name__ == "__main__":
    main()
