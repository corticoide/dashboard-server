from sqlalchemy import create_engine, inspect
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
