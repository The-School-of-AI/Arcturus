"""Tests for routers/studio.py request handling behavior."""

import asyncio

from routers import studio as studio_router


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_create_artifact_forwards_title(monkeypatch):
    captured = {}

    class FakeOrchestrator:
        async def generate_outline(self, **kwargs):
            captured.update(kwargs)
            return {"ok": True}

    monkeypatch.setattr(studio_router, "_get_orchestrator", lambda: FakeOrchestrator())

    request = studio_router.CreateArtifactRequest(
        prompt="create slides",
        title="Q2 Business Review",
    )
    result = _run(studio_router._create_artifact(request, studio_router.ArtifactType.slides))

    assert result == {"ok": True}
    assert captured["title"] == "Q2 Business Review"


def test_approve_outline_with_rejected_flag_skips_generation(monkeypatch):
    calls = {"approve": 0, "reject": 0}

    class FakeOrchestrator:
        async def approve_and_generate_draft(self, **kwargs):
            calls["approve"] += 1
            return {"status": "approved"}

        def reject_outline(self, **kwargs):
            calls["reject"] += 1
            return {"status": "rejected"}

    monkeypatch.setattr(studio_router, "_get_orchestrator", lambda: FakeOrchestrator())

    request = studio_router.ApproveOutlineRequest(approved=False, modifications={"title": "Rework"})
    result = _run(studio_router.approve_outline("artifact-1", request))

    assert result["status"] == "rejected"
    assert calls["approve"] == 0
    assert calls["reject"] == 1
