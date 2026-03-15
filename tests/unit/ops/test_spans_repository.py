"""Unit tests for ops.admin.spans_repository – orphan trace filtering and deletion."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, call

from ops.admin.spans_repository import (
    SpansRepository,
    _traces_add_fields_stage,
    _traces_project_stage,
)


def _make_span(trace_id: str, name: str, session_id: str | None = None, run_id: str | None = None) -> dict:
    """Build a span document matching the MongoDB schema."""
    now = datetime.utcnow()
    attrs: dict = {}
    if session_id is not None:
        attrs["session_id"] = session_id
    if run_id is not None:
        attrs["run_id"] = run_id
    return {
        "trace_id": trace_id,
        "span_id": "aabbccdd",
        "parent_span_id": None,
        "name": name,
        "start_time": now,
        "end_time": now + timedelta(milliseconds=50),
        "duration_ms": 50.0,
        "attributes": attrs,
        "status": "ok",
    }


class TestGetTracesPipelineContainsOrphanFilter:
    """get_traces() pipeline must contain a $match that rejects null session_id."""

    def test_pipeline_includes_session_id_filter(self):
        coll = MagicMock()
        coll.aggregate.return_value = iter([])
        repo = SpansRepository(coll)

        repo.get_traces(limit=10)

        pipeline = coll.aggregate.call_args[0][0]
        session_match = {"$match": {"session_id": {"$ne": None}}}
        assert session_match in pipeline

    def test_session_filter_is_after_add_fields(self):
        coll = MagicMock()
        coll.aggregate.return_value = iter([])
        repo = SpansRepository(coll)

        repo.get_traces(limit=10)

        pipeline = coll.aggregate.call_args[0][0]
        add_fields_idx = next(
            i for i, stage in enumerate(pipeline) if "$addFields" in stage
        )
        session_match_idx = next(
            i
            for i, stage in enumerate(pipeline)
            if stage == {"$match": {"session_id": {"$ne": None}}}
        )
        assert session_match_idx > add_fields_idx

    def test_session_filter_is_before_project(self):
        coll = MagicMock()
        coll.aggregate.return_value = iter([])
        repo = SpansRepository(coll)

        repo.get_traces(limit=10)

        pipeline = coll.aggregate.call_args[0][0]
        project_idx = next(
            i for i, stage in enumerate(pipeline) if "$project" in stage
        )
        session_match_idx = next(
            i
            for i, stage in enumerate(pipeline)
            if stage == {"$match": {"session_id": {"$ne": None}}}
        )
        assert session_match_idx < project_idx


class TestDeleteOrphanTraces:
    """delete_orphan_traces() should remove spans with no session/run identity."""

    def test_deletes_orphan_trace_ids(self):
        orphan_results = [{"_id": "trace_orphan_1"}, {"_id": "trace_orphan_2"}]
        coll = MagicMock()
        coll.aggregate.return_value = iter(orphan_results)
        coll.delete_many.return_value = MagicMock(deleted_count=5)
        repo = SpansRepository(coll)

        deleted = repo.delete_orphan_traces()

        assert deleted == 5
        coll.delete_many.assert_called_once_with(
            {"trace_id": {"$in": ["trace_orphan_1", "trace_orphan_2"]}}
        )

    def test_returns_zero_when_no_orphans(self):
        coll = MagicMock()
        coll.aggregate.return_value = iter([])
        repo = SpansRepository(coll)

        deleted = repo.delete_orphan_traces()

        assert deleted == 0
        coll.delete_many.assert_not_called()

    def test_aggregation_pipeline_groups_by_trace_id(self):
        coll = MagicMock()
        coll.aggregate.return_value = iter([])
        repo = SpansRepository(coll)

        repo.delete_orphan_traces()

        pipeline = coll.aggregate.call_args[0][0]
        group_stage = pipeline[0]
        assert "$group" in group_stage
        assert group_stage["$group"]["_id"] == "$trace_id"

    def test_aggregation_filters_orphans_only(self):
        coll = MagicMock()
        coll.aggregate.return_value = iter([])
        repo = SpansRepository(coll)

        repo.delete_orphan_traces()

        pipeline = coll.aggregate.call_args[0][0]
        match_stage = pipeline[1]
        assert "$match" in match_stage
        assert match_stage["$match"]["has_identity"] == 0
