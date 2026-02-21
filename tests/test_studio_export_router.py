"""Tests for routers/studio.py — export and theme endpoints."""

import asyncio
import json

import pytest
from fastapi import HTTPException

from routers import studio as studio_router

_UUID_1 = "00000000-0000-0000-0000-000000000001"
_UUID_JOB = "00000000-0000-0000-0000-000000000099"


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_export_artifact_success(monkeypatch):
    class FakeOrchestrator:
        async def export_artifact(self, artifact_id, export_format, theme_id=None):
            return {"id": _UUID_JOB, "status": "completed", "format": "pptx"}

    monkeypatch.setattr(studio_router, "_get_orchestrator", lambda: FakeOrchestrator())

    request = studio_router.ExportArtifactRequest(format="pptx")
    result = _run(studio_router.export_artifact(_UUID_1, request))
    assert result["status"] == "completed"
    assert result["format"] == "pptx"


def test_export_artifact_invalid_format(monkeypatch):
    class FakeOrchestrator:
        async def export_artifact(self, **kwargs):
            return {}

    monkeypatch.setattr(studio_router, "_get_orchestrator", lambda: FakeOrchestrator())

    request = studio_router.ExportArtifactRequest(format="pdf")
    with pytest.raises(HTTPException) as exc_info:
        _run(studio_router.export_artifact(_UUID_1, request))
    assert exc_info.value.status_code == 400
    assert "Unsupported export format" in exc_info.value.detail


def test_export_artifact_not_found(monkeypatch):
    class FakeOrchestrator:
        async def export_artifact(self, artifact_id, export_format, theme_id=None):
            raise ValueError(f"Artifact not found: {artifact_id}")

    monkeypatch.setattr(studio_router, "_get_orchestrator", lambda: FakeOrchestrator())

    request = studio_router.ExportArtifactRequest(format="pptx")
    with pytest.raises(HTTPException) as exc_info:
        _run(studio_router.export_artifact(_UUID_1, request))
    assert exc_info.value.status_code == 404


def test_list_exports_success(monkeypatch, tmp_path):
    from core.studio.storage import StudioStorage
    storage = StudioStorage(base_dir=tmp_path / "studio")
    monkeypatch.setattr(studio_router, "get_studio_storage", lambda: storage)

    result = _run(studio_router.list_exports(_UUID_1))
    assert result == []


def test_get_export_job_success(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from core.schemas.studio_schema import ExportJob, ExportFormat, ExportStatus
    from core.studio.storage import StudioStorage

    storage = StudioStorage(base_dir=tmp_path / "studio")
    job = ExportJob(
        id=_UUID_JOB,
        artifact_id=_UUID_1,
        format=ExportFormat.pptx,
        status=ExportStatus.completed,
        created_at=datetime.now(timezone.utc),
    )
    storage.save_export_job(job)
    monkeypatch.setattr(studio_router, "get_studio_storage", lambda: storage)

    result = _run(studio_router.get_export_job(_UUID_1, _UUID_JOB))
    assert result["id"] == _UUID_JOB
    assert result["status"] == "completed"


def test_get_export_job_not_found(monkeypatch, tmp_path):
    from core.studio.storage import StudioStorage
    storage = StudioStorage(base_dir=tmp_path / "studio")
    monkeypatch.setattr(studio_router, "get_studio_storage", lambda: storage)

    with pytest.raises(HTTPException) as exc_info:
        _run(studio_router.get_export_job(_UUID_1, _UUID_JOB))
    assert exc_info.value.status_code == 404


def test_download_export_success(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from core.schemas.studio_schema import ExportJob, ExportFormat, ExportStatus
    from core.studio.storage import StudioStorage

    storage = StudioStorage(base_dir=tmp_path / "studio")
    output_path = storage.get_export_file_path(_UUID_1, _UUID_JOB, "pptx")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"fake pptx content")

    job = ExportJob(
        id=_UUID_JOB,
        artifact_id=_UUID_1,
        format=ExportFormat.pptx,
        status=ExportStatus.completed,
        output_uri=str(output_path),
        created_at=datetime.now(timezone.utc),
    )
    storage.save_export_job(job)
    monkeypatch.setattr(studio_router, "get_studio_storage", lambda: storage)

    result = _run(studio_router.download_export(_UUID_1, _UUID_JOB))
    from fastapi.responses import FileResponse
    assert isinstance(result, FileResponse)


def test_list_themes():
    result = _run(studio_router.list_themes_endpoint())
    assert len(result) == 8
    assert any(t["id"] == "corporate-blue" for t in result)


def test_export_artifact_invalid_artifact_id():
    request = studio_router.ExportArtifactRequest(format="pptx")
    with pytest.raises(HTTPException) as exc_info:
        _run(studio_router.export_artifact("../etc/passwd", request))
    assert exc_info.value.status_code == 400
    assert "Invalid artifact_id" in exc_info.value.detail


def test_get_artifact_invalid_id_format():
    with pytest.raises(HTTPException) as exc_info:
        _run(studio_router.get_artifact("not-a-uuid"))
    assert exc_info.value.status_code == 400


def test_get_export_job_global(monkeypatch, tmp_path):
    from datetime import datetime, timezone
    from core.schemas.studio_schema import ExportJob, ExportFormat, ExportStatus
    from core.studio.storage import StudioStorage

    storage = StudioStorage(base_dir=tmp_path / "studio")
    job = ExportJob(
        id=_UUID_JOB,
        artifact_id=_UUID_1,
        format=ExportFormat.pptx,
        status=ExportStatus.completed,
        created_at=datetime.now(timezone.utc),
    )
    storage.save_export_job(job)
    monkeypatch.setattr(studio_router, "get_studio_storage", lambda: storage)

    result = _run(studio_router.get_export_job_global(_UUID_JOB))
    assert result["id"] == _UUID_JOB
