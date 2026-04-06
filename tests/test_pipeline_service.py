"""Test pipeline execution service with comprehensive coverage."""
import pytest
import json
import tempfile
import os
from pathlib import Path
from datetime import datetime

from backend.models.pipeline import (
    Pipeline,
    PipelineStep,
    PipelineRun,
    PipelineStepRun,
)
from backend.services.pipeline_service import interpolate, run_pipeline
import backend.models.pipeline  # noqa: F401


# ── Test interpolate function ────────────────────────────────────────────────────


class TestInterpolate:
    """Tests for variable interpolation in config dicts."""

    def test_interpolate_basic_strings(self):
        """Replace {VAR} with context values in simple config."""
        config = {"src": "{BASE}/file.txt", "dst": "{DEST}"}
        ctx = {"BASE": "/tmp", "DEST": "/mnt/nas"}
        result = interpolate(config, ctx)
        assert result["src"] == "/tmp/file.txt"
        assert result["dst"] == "/mnt/nas"

    def test_interpolate_nested_dict(self):
        """Replace variables in nested dicts recursively."""
        config = {"outer": {"inner": "{VAR}", "other": "static"}}
        result = interpolate(config, {"VAR": "hello"})
        assert result["outer"]["inner"] == "hello"
        assert result["outer"]["other"] == "static"

    def test_interpolate_deeply_nested(self):
        """Replace variables in multiple nesting levels."""
        config = {
            "l1": {
                "l2": {
                    "l3": "{DEEP}",
                    "l3b": "{OTHER}",
                }
            }
        }
        result = interpolate(config, {"DEEP": "value", "OTHER": "other"})
        assert result["l1"]["l2"]["l3"] == "value"
        assert result["l1"]["l2"]["l3b"] == "other"

    def test_interpolate_missing_var_left_as_is(self):
        """Missing variables remain as {VAR} placeholders."""
        config = {"path": "{MISSING}"}
        result = interpolate(config, {})
        assert result["path"] == "{MISSING}"

    def test_interpolate_multiple_vars_in_one_string(self):
        """Replace multiple variables in a single string."""
        config = {"path": "{DIR}/{FILE}.{EXT}"}
        result = interpolate(config, {"DIR": "home", "FILE": "test", "EXT": "txt"})
        assert result["path"] == "home/test.txt"

    def test_interpolate_empty_context(self):
        """With empty context, variables remain unchanged."""
        config = {"url": "https://{HOST}:{PORT}/{PATH}"}
        result = interpolate(config, {})
        assert result["url"] == "https://{HOST}:{PORT}/{PATH}"

    def test_interpolate_non_string_values_preserved(self):
        """Non-string values (int, bool, None) pass through unchanged."""
        config = {"count": 42, "enabled": True, "value": None, "name": "{VAR}"}
        result = interpolate(config, {"VAR": "test"})
        assert result["count"] == 42
        assert result["enabled"] is True
        assert result["value"] is None
        assert result["name"] == "test"

    def test_interpolate_empty_config(self):
        """Empty config returns empty dict."""
        result = interpolate({}, {"VAR": "value"})
        assert result == {}

    def test_interpolate_partial_replacement(self):
        """Replace only variables that exist in context."""
        config = {"path": "{FOUND}/{MISSING}"}
        result = interpolate(config, {"FOUND": "exists"})
        assert result["path"] == "exists/{MISSING}"

    def test_interpolate_list_values_not_interpolated(self):
        """Lists are preserved as-is (not recursed into)."""
        config = {"args": ["{VAR}", "literal"]}
        result = interpolate(config, {"VAR": "test"})
        # Lists are NOT recursed, so {VAR} stays as string in list
        assert result["args"] == ["{VAR}", "literal"]


# ── Helper to build pipelines ────────────────────────────────────────────────────


def _make_pipeline(db, steps_data):
    """Helper to create a pipeline with steps in the test DB."""
    p = Pipeline(name=f"test-pipeline-{id(steps_data)}", description="")
    db.add(p)
    db.flush()
    for i, sd in enumerate(steps_data):
        step = PipelineStep(
            pipeline_id=p.id,
            order=i,
            name=sd.get("name", f"step-{i}"),
            step_type=sd["step_type"],
            config=json.dumps(sd.get("config", {})),
            on_success=sd.get("on_success", "continue"),
            on_failure=sd.get("on_failure", "stop"),
        )
        db.add(step)
    db.commit()
    return p


# ── Test pipeline execution ──────────────────────────────────────────────────────


class TestRunPipeline:
    """Tests for full pipeline execution flow."""

    def test_run_pipeline_not_found(self, db_session):
        """Raise ValueError if pipeline does not exist."""
        with pytest.raises(ValueError, match="not found"):
            run_pipeline(999, "test_user", db_session)

    def test_run_pipeline_creates_run_record(self, db_session):
        """Creating a run creates a PipelineRun record with correct fields."""
        p = _make_pipeline(db_session, [
            {"step_type": "module", "config": {"module": "log", "message": "test"}},
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.pipeline_id == p.id
        assert run.triggered_by == "test_user"
        assert run.status in ["success", "failed"]
        assert run.started_at is not None
        assert run.ended_at is not None

    def test_run_pipeline_all_steps_success(self, db_session):
        """When all steps succeed, overall status is 'success'."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "out.txt")
            p = _make_pipeline(db_session, [
                {
                    "step_type": "module",
                    "config": {
                        "module": "write_file",
                        "path": path,
                        "content": "hello",
                        "mode": "overwrite",
                    },
                },
                {
                    "step_type": "module",
                    "config": {"module": "log", "message": "done"},
                },
            ])
            run = run_pipeline(p.id, "test_user", db_session)
            assert run.status == "success"
            # Verify all step runs are success
            step_runs = (
                db_session.query(PipelineStepRun)
                .filter_by(run_id=run.id)
                .order_by(PipelineStepRun.step_order)
                .all()
            )
            assert len(step_runs) == 2
            assert all(sr.status == "success" for sr in step_runs)
            # Verify file was written
            assert Path(path).read_text() == "hello"

    def test_run_pipeline_fails_on_module_error(self, db_session):
        """When a step fails, overall status is 'failed'."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {"module": "check_exists", "path": "/nonexistent/path", "type": "file"},
                "on_failure": "stop",
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "failed"
        step_run = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert step_run.status == "failed"
        assert step_run.exit_code == 1
        assert "not found" in step_run.output.lower() or "Not found" in step_run.output

    def test_run_pipeline_stops_on_failure(self, db_session):
        """When on_failure='stop', subsequent steps are skipped."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {
                    "module": "check_exists",
                    "path": "/nonexistent/path",
                    "type": "file",
                },
                "on_failure": "stop",
            },
            {
                "step_type": "module",
                "config": {"module": "log", "message": "should not run"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "failed"
        step_runs = (
            db_session.query(PipelineStepRun)
            .filter_by(run_id=run.id)
            .order_by(PipelineStepRun.step_order)
            .all()
        )
        assert len(step_runs) == 2
        assert step_runs[0].status == "failed"
        assert step_runs[1].status == "skipped"
        assert step_runs[1].exit_code is None

    def test_run_pipeline_continues_on_failure(self, db_session):
        """When on_failure='continue', next steps run."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {
                    "module": "check_exists",
                    "path": "/nonexistent",
                    "type": "file",
                },
                "on_failure": "continue",
            },
            {
                "step_type": "module",
                "config": {"module": "log", "message": "after error"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        # Pipeline status is failed (because one step failed), but next step ran
        assert run.status == "failed"
        step_runs = (
            db_session.query(PipelineStepRun)
            .filter_by(run_id=run.id)
            .order_by(PipelineStepRun.step_order)
            .all()
        )
        assert step_runs[0].status == "failed"
        assert step_runs[1].status == "success"

    def test_run_pipeline_with_shell_step(self, db_session):
        """Execute shell commands via step_type='shell'."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "shell",
                "config": {"command": "echo hello_pipeline"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "success"
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "success"
        assert sr.exit_code == 0
        assert "hello_pipeline" in sr.output

    def test_run_pipeline_shell_failure(self, db_session):
        """Shell command with non-zero exit code marks step as failed."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "shell",
                "config": {"command": "false"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "failed"
        assert sr.exit_code != 0

    def test_run_pipeline_context_interpolation(self, db_session):
        """Variables from load_env module are available to subsequent steps."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ctx.txt")
            env_path = os.path.join(tmp, ".env")
            with open(env_path, "w") as f:
                f.write(f"OUT_PATH={path}\n")
            p = _make_pipeline(db_session, [
                {
                    "step_type": "module",
                    "config": {"module": "load_env", "path": env_path},
                },
                {
                    "step_type": "module",
                    "config": {
                        "module": "write_file",
                        "path": "{OUT_PATH}",
                        "content": "ctx works",
                        "mode": "overwrite",
                    },
                },
            ])
            run = run_pipeline(p.id, "test_user", db_session)
            assert run.status == "success"
            assert Path(path).read_text() == "ctx works"

    def test_run_pipeline_multiple_context_vars(self, db_session):
        """Multiple context variables are interpolated."""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "src.txt")
            dst = os.path.join(tmp, "dst.txt")
            env_path = os.path.join(tmp, ".env")
            Path(src).write_text("hello")
            with open(env_path, "w") as f:
                f.write(f"SRC={src}\nDST={dst}\n")
            p = _make_pipeline(db_session, [
                {"step_type": "module", "config": {"module": "load_env", "path": env_path}},
                {
                    "step_type": "module",
                    "config": {"module": "copy_file", "src": "{SRC}", "dst": "{DST}"},
                },
            ])
            run = run_pipeline(p.id, "test_user", db_session)
            assert run.status == "success"
            assert Path(dst).read_text() == "hello"

    def test_run_pipeline_stores_step_runs_in_order(self, db_session):
        """All steps are recorded as PipelineStepRun with correct order."""
        p = _make_pipeline(db_session, [
            {"step_type": "module", "config": {"module": "log", "message": "step0"}},
            {"step_type": "module", "config": {"module": "log", "message": "step1"}},
            {"step_type": "module", "config": {"module": "log", "message": "step2"}},
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        step_runs = (
            db_session.query(PipelineStepRun)
            .filter_by(run_id=run.id)
            .order_by(PipelineStepRun.step_order)
            .all()
        )
        assert len(step_runs) == 3
        assert [sr.step_order for sr in step_runs] == [0, 1, 2]

    def test_run_pipeline_empty_pipeline(self, db_session):
        """Pipeline with no steps has status 'success'."""
        p = Pipeline(name="empty-pipeline", description="")
        db_session.add(p)
        db_session.commit()
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "success"
        step_runs = db_session.query(PipelineStepRun).filter_by(run_id=run.id).all()
        assert len(step_runs) == 0

    def test_run_pipeline_timestamps(self, db_session):
        """Run and step runs have accurate timestamps."""
        from datetime import timedelta
        p = _make_pipeline(db_session, [
            {"step_type": "module", "config": {"module": "log", "message": "test"}},
        ])
        before = datetime.utcnow() - timedelta(seconds=1)
        run = run_pipeline(p.id, "test_user", db_session)
        after = datetime.utcnow() + timedelta(seconds=1)

        assert before <= run.started_at <= after
        assert before <= run.ended_at <= after

        step_run = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert before <= step_run.started_at <= after
        assert before <= step_run.ended_at <= after


class TestRunPipelineEdgeCases:
    """Edge cases and error handling."""

    def test_run_pipeline_unknown_module(self, db_session):
        """Unknown module name results in failed step."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {"module": "nonexistent_module"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "failed"
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "failed"
        assert "Unknown module" in sr.output

    def test_run_pipeline_unknown_step_type(self, db_session):
        """Unknown step_type is handled gracefully."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "unknown_type",
                "config": {},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "failed"
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "failed"
        assert "Unknown step_type" in sr.output

    def test_run_pipeline_module_missing_required_config(self, db_session):
        """Module called without required config key returns error."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {"module": "write_file"},  # missing 'path'
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "failed"
        assert sr.exit_code == 1

    def test_run_pipeline_first_step_always_runs(self, db_session):
        """First step always runs regardless of prev_exit_code."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {"module": "log", "message": "first"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "success"

    def test_run_pipeline_success_followed_by_on_success_stop(self, db_session):
        """When on_success='stop', next step skips."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {"module": "log", "message": "first"},
                "on_success": "stop",
            },
            {
                "step_type": "module",
                "config": {"module": "log", "message": "second"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        step_runs = (
            db_session.query(PipelineStepRun)
            .filter_by(run_id=run.id)
            .order_by(PipelineStepRun.step_order)
            .all()
        )
        assert step_runs[0].status == "success"
        assert step_runs[1].status == "skipped"

    def test_run_pipeline_stores_output(self, db_session):
        """Step output is captured and stored."""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.txt")
            p = _make_pipeline(db_session, [
                {
                    "step_type": "module",
                    "config": {
                        "module": "write_file",
                        "path": path,
                        "content": "data",
                        "mode": "overwrite",
                    },
                },
            ])
            run = run_pipeline(p.id, "test_user", db_session)
            sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
            assert sr.output is not None
            assert len(sr.output) > 0

    def test_run_pipeline_module_with_no_module_key(self, db_session):
        """Module config without 'module' key returns error."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "module",
                "config": {"path": "/tmp"},  # no 'module' key
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "failed"
        assert "No 'module' key" in sr.output


class TestRunPipelineShellSteps:
    """Tests for shell command execution."""

    def test_run_pipeline_shell_with_pipes(self, db_session):
        """Shell commands with pipes work correctly."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "shell",
                "config": {"command": "echo 'line1\\nline2' | wc -l"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        assert run.status == "success"
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.exit_code == 0

    def test_run_pipeline_shell_timeout(self, db_session):
        """Shell command timeout returns error."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "shell",
                "config": {"command": "timeout 0.5 sleep 10"},  # Will timeout
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        assert sr.status == "failed"
        assert sr.exit_code != 0

    def test_run_pipeline_shell_with_stderr(self, db_session):
        """Shell stderr is captured in output."""
        p = _make_pipeline(db_session, [
            {
                "step_type": "shell",
                "config": {"command": "echo 'error' >&2"},
            },
        ])
        run = run_pipeline(p.id, "test_user", db_session)
        sr = db_session.query(PipelineStepRun).filter_by(run_id=run.id).first()
        # stderr is captured
        assert "error" in sr.output


class TestRunPipelineModuleSteps:
    """Tests for module-based steps."""

    def test_run_pipeline_multiple_module_steps(self, db_session):
        """Multiple module steps execute in order."""
        with tempfile.TemporaryDirectory() as tmp:
            dir1 = os.path.join(tmp, "dir1")
            dir2 = os.path.join(tmp, "dir2")
            p = _make_pipeline(db_session, [
                {"step_type": "module", "config": {"module": "mkdir", "path": dir1}},
                {"step_type": "module", "config": {"module": "mkdir", "path": dir2}},
            ])
            run = run_pipeline(p.id, "test_user", db_session)
            assert run.status == "success"
            assert Path(dir1).exists() and Path(dir2).exists()

    def test_run_pipeline_compress_module(self, db_session):
        """compress module works in pipeline."""
        with tempfile.TemporaryDirectory() as tmp:
            src = os.path.join(tmp, "file.txt")
            archive = os.path.join(tmp, "archive.tar.gz")
            Path(src).write_text("content")
            p = _make_pipeline(db_session, [
                {
                    "step_type": "module",
                    "config": {
                        "module": "compress",
                        "src": src,
                        "dst": archive,
                        "format": "tar.gz",
                    },
                },
            ])
            run = run_pipeline(p.id, "test_user", db_session)
            assert run.status == "success"
            assert Path(archive).exists()

    def test_run_pipeline_delay_module(self, db_session):
        """delay module pauses execution."""
        import time
        p = _make_pipeline(db_session, [
            {"step_type": "module", "config": {"module": "delay", "seconds": 0.1}},
        ])
        start = time.time()
        run = run_pipeline(p.id, "test_user", db_session)
        elapsed = time.time() - start
        assert elapsed >= 0.09
        assert run.status == "success"
