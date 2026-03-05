from __future__ import annotations

import tempfile
from pathlib import Path

from notion_manager.execution_tracker import ExecutionTracker


class TestExecutionTracker:
    def setup_method(self):
        self._tmpdir = tempfile.mkdtemp()
        self.db_path = str(Path(self._tmpdir) / "test_exec.db")
        self.tracker = ExecutionTracker(db_path=self.db_path)

    def teardown_method(self):
        self.tracker.close()

    def test_wal_mode(self):
        row = self.tracker._conn.execute("PRAGMA journal_mode").fetchone()
        assert row[0] == "wal"

    def test_execution_lifecycle(self):
        exec_id = self.tracker.start("summarizer", {"page_id": "abc"})
        assert exec_id > 0
        self.tracker.finish(exec_id, {"summary": "done"})
        history = self.tracker.get_history("summarizer")
        assert len(history) == 1
        assert history[0]["status"] == "success"
        assert history[0]["duration_ms"] >= 0
        assert history[0]["plugin_name"] == "summarizer"

    def test_execution_failure(self):
        exec_id = self.tracker.start("tagger")
        self.tracker.fail(exec_id, "Connection timeout")
        history = self.tracker.get_history("tagger")
        assert len(history) == 1
        assert history[0]["status"] == "error"
        assert history[0]["error_msg"] == "Connection timeout"

    def test_get_stats_accuracy(self):
        # 2 successes, 1 failure
        eid1 = self.tracker.start("test_plugin")
        self.tracker.finish(eid1, {})
        eid2 = self.tracker.start("test_plugin")
        self.tracker.finish(eid2, {})
        eid3 = self.tracker.start("test_plugin")
        self.tracker.fail(eid3, "error")

        stats = self.tracker.get_stats("test_plugin")
        assert stats["total"] == 3
        assert stats["successes"] == 2
        assert stats["success_rate"] == 66.67

    def test_history_pagination(self):
        for i in range(25):
            eid = self.tracker.start("paginated")
            self.tracker.finish(eid, {"i": i})

        page = self.tracker.get_history("paginated", limit=10, offset=10)
        assert len(page) == 10

    def test_context_manager_success(self):
        with self.tracker.track("ctx_plugin", {"key": "val"}) as ctx:
            ctx["result"] = {"output": "ok"}

        history = self.tracker.get_history("ctx_plugin")
        assert len(history) == 1
        assert history[0]["status"] == "success"

    def test_context_manager_error(self):
        try:
            with self.tracker.track("ctx_err") as ctx:
                raise ValueError("test error")
        except ValueError:
            pass

        history = self.tracker.get_history("ctx_err")
        assert len(history) == 1
        assert history[0]["status"] == "error"
        assert "test error" in history[0]["error_msg"]

    def test_get_history_all(self):
        eid1 = self.tracker.start("plugin_a")
        self.tracker.finish(eid1, {})
        eid2 = self.tracker.start("plugin_b")
        self.tracker.finish(eid2, {})

        history = self.tracker.get_history()
        assert len(history) == 2
