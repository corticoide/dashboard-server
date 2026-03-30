from sqlalchemy import create_engine, inspect, text
from backend.database import Base
from backend.models.execution_log import ExecutionLog  # noqa: F401


def test_execution_log_index_declarations():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    index_columns = {
        idx["column_names"][0]
        for idx in inspector.get_indexes("execution_logs")
    }
    assert "started_at" in index_columns, "missing index on started_at"
    assert "username" in index_columns, "missing index on username"
    assert "exit_code" in index_columns, "missing index on exit_code"


def test_composite_username_started_at_index_exists():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='execution_logs'")
        ).fetchall()
    index_names = [r[0] for r in result]
    assert any(
        ("username" in n and "started_at" in n) or "username_started_at" in n
        for n in index_names
    ), f"Composite index not found, got: {index_names}"
