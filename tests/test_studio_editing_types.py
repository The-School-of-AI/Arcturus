"""Tests for core/studio/editing/types.py — Patch and Target model validation."""

import pytest
from pydantic import ValidationError

from core.studio.editing.types import (
    Patch,
    PatchOp,
    PatchOpType,
    SectionTarget,
    SlideTarget,
    TabTarget,
)


class TestPatchOp:
    def test_patch_op_set_valid(self):
        op = PatchOp(op=PatchOpType.SET, path="title", value="New Title")
        assert op.op == PatchOpType.SET
        assert op.path == "title"
        assert op.value == "New Title"

    def test_patch_op_insert_after_valid(self):
        op = PatchOp(
            op=PatchOpType.INSERT_AFTER,
            path="elements",
            item={"id": "e99", "type": "body", "content": "New paragraph"},
            id_key="id",
        )
        assert op.op == PatchOpType.INSERT_AFTER
        assert op.item["id"] == "e99"
        assert op.id_key == "id"

    def test_patch_op_delete_valid(self):
        op = PatchOp(op=PatchOpType.DELETE, path="elements[2]")
        assert op.op == PatchOpType.DELETE
        assert op.path == "elements[2]"

    def test_patch_op_unknown_op_rejected(self):
        with pytest.raises(ValidationError):
            PatchOp(op="RENAME", path="title", value="x")


class TestPatchEnvelope:
    def test_patch_envelope_valid(self):
        patch = Patch(
            artifact_type="slides",
            target={"kind": "slide_index", "index": 3},
            ops=[PatchOp(op=PatchOpType.SET, path="title", value="Updated")],
            summary="Update slide 3 title",
        )
        assert patch.artifact_type == "slides"
        assert len(patch.ops) == 1
        assert patch.summary == "Update slide 3 title"

    def test_patch_envelope_empty_ops_rejected(self):
        with pytest.raises(ValidationError):
            Patch(
                artifact_type="slides",
                target={"kind": "slide_index", "index": 1},
                ops=[],
                summary="Empty ops should fail",
            )


class TestTargets:
    def test_slide_target_variants(self):
        by_index = SlideTarget(kind="slide_index", index=3)
        assert by_index.kind == "slide_index"
        assert by_index.index == 3

        by_id = SlideTarget(kind="slide_id", id="s5")
        assert by_id.id == "s5"

        by_element = SlideTarget(kind="slide_element", element_id="e10")
        assert by_element.element_id == "e10"

    def test_tab_target_cell_range(self):
        target = TabTarget(kind="cell_range", tab_name="Revenue", a1="B2:D10")
        assert target.kind == "cell_range"
        assert target.tab_name == "Revenue"
        assert target.a1 == "B2:D10"

    def test_section_target_heading_contains(self):
        target = SectionTarget(kind="heading_contains", text="Introduction")
        assert target.kind == "heading_contains"
        assert target.text == "Introduction"

    def test_section_target_by_id(self):
        target = SectionTarget(kind="section_id", id="sec1")
        assert target.kind == "section_id"
        assert target.id == "sec1"
