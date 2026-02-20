#!/usr/bin/env python3
"""
Manual test script for Forge Phase 1.
Exercises the full pipeline (outline -> approve -> draft) with a mocked LLM,
then tests all API endpoints against the live server.

Usage:
    # Part 1: Direct pipeline test (no server needed)
    uv run python scripts/manual_test_forge.py --pipeline

    # Part 2: API endpoint tests (server must be running on :8000)
    uv run python scripts/manual_test_forge.py --api

    # Both:
    uv run python scripts/manual_test_forge.py --all
"""
import argparse
import asyncio
import json
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
INFO = "\033[94mINFO\033[0m"
HEADER = "\033[1;36m"
RESET = "\033[0m"

results = {"passed": 0, "failed": 0}


def check(label, condition, detail=""):
    if condition:
        results["passed"] += 1
        print(f"  {PASS} {label}")
    else:
        results["failed"] += 1
        print(f"  {FAIL} {label}" + (f" — {detail}" if detail else ""))


# ─────────────────────────────────────────────
# Part 1: Direct pipeline test (mocked LLM)
# ─────────────────────────────────────────────

MOCK_OUTLINE_JSON = json.dumps({
    "title": "Acme AI Pitch Deck",
    "items": [
        {"id": "1", "title": "Title Slide", "description": "Company intro"},
        {"id": "2", "title": "Problem", "description": "Pain points in enterprise"},
        {"id": "3", "title": "Solution", "description": "AI-powered automation"},
        {"id": "4", "title": "Market", "description": "TAM/SAM/SOM analysis"},
        {"id": "5", "title": "Ask", "description": "Funding request"},
    ]
})

MOCK_SLIDES_DRAFT_JSON = json.dumps({
    "deck_title": "Acme AI Pitch Deck",
    "subtitle": "Transforming Enterprise Automation",
    "slides": [
        {
            "id": "s1", "slide_type": "title", "title": "Acme AI",
            "elements": [
                {"id": "e1", "type": "title", "content": "Acme AI"},
                {"id": "e2", "type": "subtitle", "content": "Series A Pitch Deck"}
            ],
            "speaker_notes": "Introduce the company."
        },
        {
            "id": "s2", "slide_type": "content", "title": "The Problem",
            "elements": [
                {"id": "e3", "type": "body", "content": "Enterprises waste 40% of operational time on manual processes."},
                {"id": "e4", "type": "bullet_list", "content": ["Manual data entry", "Fragmented tools", "No automation"]}
            ],
            "speaker_notes": "Emphasize pain points."
        },
        {
            "id": "s3", "slide_type": "content", "title": "Our Solution",
            "elements": [
                {"id": "e5", "type": "body", "content": "AI agents that automate end-to-end workflows."}
            ],
            "speaker_notes": "Demo the product."
        }
    ],
    "metadata": {"audience": "investors", "tone": "professional"}
})

MOCK_DOC_DRAFT_JSON = json.dumps({
    "doc_title": "Technical Specification",
    "doc_type": "technical_spec",
    "abstract": "This document outlines the migration plan.",
    "sections": [
        {
            "id": "sec1", "heading": "Introduction", "level": 1,
            "content": "The current system has reached its limits.",
            "subsections": [], "citations": []
        }
    ],
    "bibliography": [],
    "metadata": {"audience": "engineering"}
})

MOCK_SHEET_DRAFT_JSON = json.dumps({
    "workbook_title": "Financial Model",
    "tabs": [
        {
            "id": "tab1", "name": "Revenue",
            "headers": ["Month", "Users", "MRR"],
            "rows": [["Jan", 1000, 50000], ["Feb", 1100, 55000]],
            "formulas": {},
            "column_widths": [120, 80, 100]
        }
    ],
    "assumptions": "10% monthly growth",
    "metadata": {"currency": "USD"}
})


async def test_pipeline():
    import tempfile
    from pathlib import Path
    from unittest.mock import patch

    from core.studio.storage import StudioStorage
    from core.studio.orchestrator import ForgeOrchestrator
    from core.schemas.studio_schema import ArtifactType, OutlineStatus

    tmpdir = Path(tempfile.mkdtemp()) / "studio"
    storage = StudioStorage(base_dir=tmpdir)
    orchestrator = ForgeOrchestrator(storage)

    # ── Test 1: Generate slides outline ──
    print(f"\n{HEADER}=== Test: Generate Slides Outline ==={RESET}")

    async def mock_slides_generate(self, prompt):
        # "content architect" only appears in outline prompt, not draft prompt
        if "content architect" in prompt.lower():
            return MOCK_OUTLINE_JSON
        return MOCK_SLIDES_DRAFT_JSON

    with patch("core.model_manager.ModelManager.generate_text", mock_slides_generate):
        result = await orchestrator.generate_outline(
            prompt="Create a pitch deck for Acme AI",
            artifact_type=ArtifactType.slides,
            parameters={"audience": "investors", "slide_count": 5}
        )

    artifact_id = result["artifact_id"]
    check("Outline returned artifact_id", artifact_id is not None)
    check("Outline status is pending", result["status"] == "pending")
    check("Outline has items", len(result["outline"]["items"]) == 5)
    check("Outline title matches", result["outline"]["title"] == "Acme AI Pitch Deck")
    print(f"  {INFO} artifact_id = {artifact_id}")

    # Verify persisted
    loaded = storage.load_artifact(artifact_id)
    check("Artifact persisted to storage", loaded is not None)
    check("Persisted outline status is pending", loaded.outline.status == OutlineStatus.pending)
    check("content_tree is None before approval", loaded.content_tree is None)

    # ── Test 2: Approve and generate draft ──
    print(f"\n{HEADER}=== Test: Approve Outline & Generate Draft ==={RESET}")

    with patch("core.model_manager.ModelManager.generate_text", mock_slides_generate):
        draft_result = await orchestrator.approve_and_generate_draft(artifact_id)

    check("Draft has content_tree", draft_result.get("content_tree") is not None)
    check("content_tree has deck_title", draft_result["content_tree"].get("deck_title") == "Acme AI Pitch Deck")
    check("content_tree has slides", len(draft_result["content_tree"].get("slides", [])) == 3)
    check("Outline status is approved", draft_result["outline"]["status"] == "approved")
    check("revision_head_id is set", draft_result.get("revision_head_id") is not None)

    revision_head_id = draft_result["revision_head_id"]
    print(f"  {INFO} revision_head_id = {revision_head_id}")

    # Verify persisted
    loaded = storage.load_artifact(artifact_id)
    check("Persisted artifact has content_tree", loaded.content_tree is not None)
    check("Persisted outline is approved", loaded.outline.status == OutlineStatus.approved)

    # ── Test 3: Revisions ──
    print(f"\n{HEADER}=== Test: Revision Created ==={RESET}")

    revisions = storage.list_revisions(artifact_id)
    check("One revision exists", len(revisions) == 1)
    check("Revision ID matches head", revisions[0]["id"] == revision_head_id)
    check("Change summary is 'Initial draft'", revisions[0]["change_summary"] == "Initial draft")

    rev = storage.load_revision(artifact_id, revision_head_id)
    check("Revision has content_tree_snapshot", rev.content_tree_snapshot is not None)
    check("Snapshot has deck_title", rev.content_tree_snapshot.get("deck_title") == "Acme AI Pitch Deck")

    # ── Test 4: List artifacts ──
    print(f"\n{HEADER}=== Test: List Artifacts ==={RESET}")

    artifacts = storage.list_artifacts()
    check("One artifact in list", len(artifacts) == 1)
    check("Listed artifact has correct type", artifacts[0]["type"] == "slides")
    check("Listed artifact has correct title", artifacts[0]["title"] == "Acme AI Pitch Deck")

    # ── Test 5: Document outline + draft ──
    print(f"\n{HEADER}=== Test: Document Pipeline ==={RESET}")

    async def mock_generate_doc(self, prompt):
        if "content architect" in prompt.lower():
            return json.dumps({
                "title": "Technical Specification",
                "items": [{"id": "1", "title": "Introduction", "description": "Overview"}]
            })
        return MOCK_DOC_DRAFT_JSON

    with patch("core.model_manager.ModelManager.generate_text", mock_generate_doc):
        doc_result = await orchestrator.generate_outline(
            prompt="Write a technical spec",
            artifact_type=ArtifactType.document,
        )
    doc_id = doc_result["artifact_id"]
    check("Document outline created", doc_result["status"] == "pending")

    with patch("core.model_manager.ModelManager.generate_text", mock_generate_doc):
        doc_draft = await orchestrator.approve_and_generate_draft(doc_id)

    check("Document has content_tree", doc_draft["content_tree"] is not None)
    check("Document has doc_title", doc_draft["content_tree"]["doc_title"] == "Technical Specification")
    check("Document has sections", len(doc_draft["content_tree"]["sections"]) >= 1)

    # ── Test 6: Sheet outline + draft ──
    print(f"\n{HEADER}=== Test: Sheet Pipeline ==={RESET}")

    async def mock_generate_sheet(self, prompt):
        if "content architect" in prompt.lower():
            return json.dumps({
                "title": "Financial Model",
                "items": [{"id": "1", "title": "Revenue", "description": "Revenue projections"}]
            })
        return MOCK_SHEET_DRAFT_JSON

    with patch("core.model_manager.ModelManager.generate_text", mock_generate_sheet):
        sheet_result = await orchestrator.generate_outline(
            prompt="Create a financial model",
            artifact_type=ArtifactType.sheet,
        )
    sheet_id = sheet_result["artifact_id"]
    check("Sheet outline created", sheet_result["status"] == "pending")

    with patch("core.model_manager.ModelManager.generate_text", mock_generate_sheet):
        sheet_draft = await orchestrator.approve_and_generate_draft(sheet_id)

    check("Sheet has content_tree", sheet_draft["content_tree"] is not None)
    check("Sheet has workbook_title", sheet_draft["content_tree"]["workbook_title"] == "Financial Model")
    check("Sheet has tabs", len(sheet_draft["content_tree"]["tabs"]) >= 1)

    # ── Test 7: Reject outline ──
    print(f"\n{HEADER}=== Test: Reject Outline ==={RESET}")

    async def mock_generate_reject(self, prompt):
        return MOCK_OUTLINE_JSON

    with patch("core.model_manager.ModelManager.generate_text", mock_generate_reject):
        reject_result = await orchestrator.generate_outline(
            prompt="Create something to reject",
            artifact_type=ArtifactType.slides,
        )
    reject_id = reject_result["artifact_id"]

    rejected = orchestrator.reject_outline(reject_id)
    check("Rejected outline status", rejected["outline"]["status"] == "rejected")
    check("Rejected artifact has no content_tree", rejected.get("content_tree") is None)

    # ── Test 8: Error cases ──
    print(f"\n{HEADER}=== Test: Error Cases ==={RESET}")

    try:
        await orchestrator.approve_and_generate_draft("nonexistent-id")
        check("Nonexistent artifact raises", False, "No exception raised")
    except ValueError as e:
        check("Nonexistent artifact raises ValueError", "not found" in str(e).lower())

    # ── Test 9: Delete artifact ──
    print(f"\n{HEADER}=== Test: Delete Artifact ==={RESET}")

    storage.delete_artifact(reject_id)
    check("Deleted artifact returns None", storage.load_artifact(reject_id) is None)
    remaining = storage.list_artifacts()
    check("Remaining artifacts count correct", len(remaining) == 3)

    # ── Test 10: Title override ──
    print(f"\n{HEADER}=== Test: Title Override ==={RESET}")

    with patch("core.model_manager.ModelManager.generate_text", mock_slides_generate):
        title_result = await orchestrator.generate_outline(
            prompt="Create a deck",
            artifact_type=ArtifactType.slides,
            title="My Custom Title"
        )

    check("Title override applied", title_result["outline"]["title"] == "My Custom Title")

    # Cleanup
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)

    return artifact_id, doc_id, sheet_id


# ─────────────────────────────────────────────
# Part 2: API endpoint tests (server on :8000)
# ─────────────────────────────────────────────

async def test_api():
    import httpx

    base = "http://localhost:8000/api/studio"

    async with httpx.AsyncClient(timeout=30) as client:

        # ── GET /studio — list (may be empty or have leftover data) ──
        print(f"\n{HEADER}=== API Test: List Artifacts ==={RESET}")
        r = await client.get(base)
        check("GET /studio returns 200", r.status_code == 200)
        check("GET /studio returns list", isinstance(r.json(), list))

        # ── GET /studio/nonexistent — 404 ──
        print(f"\n{HEADER}=== API Test: Get Nonexistent Artifact ==={RESET}")
        r = await client.get(f"{base}/nonexistent-id-12345")
        check("GET nonexistent returns 404", r.status_code == 404)

        # ── POST /studio/slides — will fail (no LLM) but should return 500, not crash ──
        print(f"\n{HEADER}=== API Test: POST /studio/slides (expected LLM error) ==={RESET}")
        r = await client.post(f"{base}/slides", json={"prompt": "Test slides"})
        check("POST /studio/slides returns error (no LLM)", r.status_code == 500)
        check("Error has detail message", "detail" in r.json())
        print(f"  {INFO} Error: {r.json()['detail'][:100]}...")

        # ── POST /studio/documents — same ──
        print(f"\n{HEADER}=== API Test: POST /studio/documents (expected LLM error) ==={RESET}")
        r = await client.post(f"{base}/documents", json={"prompt": "Test doc"})
        check("POST /studio/documents returns error (no LLM)", r.status_code == 500)

        # ── POST /studio/sheets — same ──
        print(f"\n{HEADER}=== API Test: POST /studio/sheets (expected LLM error) ==={RESET}")
        r = await client.post(f"{base}/sheets", json={"prompt": "Test sheet"})
        check("POST /studio/sheets returns error (no LLM)", r.status_code == 500)

        # ── POST approve on nonexistent ──
        print(f"\n{HEADER}=== API Test: Approve Nonexistent ==={RESET}")
        r = await client.post(f"{base}/nonexistent-id/outline/approve", json={"approved": True})
        check("Approve nonexistent returns 404", r.status_code == 404)

        # ── GET revisions on nonexistent ──
        print(f"\n{HEADER}=== API Test: List Revisions Nonexistent ==={RESET}")
        r = await client.get(f"{base}/nonexistent-id/revisions")
        check("List revisions returns 200 (empty)", r.status_code == 200)
        check("Empty revisions list", r.json() == [])

        # ── Seed an artifact directly via storage and test GET ──
        print(f"\n{HEADER}=== API Test: Seed Artifact & Test GET ==={RESET}")

        from datetime import datetime, timezone
        from core.schemas.studio_schema import Artifact, ArtifactType, Outline, OutlineItem, OutlineStatus
        from shared.state import get_studio_storage

        storage = get_studio_storage()
        test_artifact = Artifact(
            id="manual-test-001",
            type=ArtifactType.slides,
            title="Manual Test Deck",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            outline=Outline(
                artifact_type=ArtifactType.slides,
                title="Manual Test Deck",
                items=[OutlineItem(id="1", title="Intro", description="Opening")],
                status=OutlineStatus.approved,
            ),
            content_tree={
                "deck_title": "Manual Test Deck",
                "slides": [{"id": "s1", "slide_type": "title", "title": "Intro",
                            "elements": [{"id": "e1", "type": "title", "content": "Hello"}]}]
            }
        )
        storage.save_artifact(test_artifact)
        print(f"  {INFO} Seeded artifact manual-test-001")

        r = await client.get(f"{base}/manual-test-001")
        check("GET seeded artifact returns 200", r.status_code == 200)
        data = r.json()
        check("Artifact ID matches", data["id"] == "manual-test-001")
        check("Artifact title matches", data["title"] == "Manual Test Deck")
        check("Artifact has content_tree", data["content_tree"] is not None)
        check("Outline is approved", data["outline"]["status"] == "approved")
        print(f"  {INFO} Artifact data: type={data['type']}, title={data['title']}")

        # ── Verify it appears in list ──
        r = await client.get(base)
        ids = [a["id"] for a in r.json()]
        check("Seeded artifact in list", "manual-test-001" in ids)

        # ── Cleanup: delete seeded artifact ──
        storage.delete_artifact("manual-test-001")
        r = await client.get(f"{base}/manual-test-001")
        check("Deleted artifact returns 404", r.status_code == 404)


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def print_summary():
    total = results["passed"] + results["failed"]
    print(f"\n{HEADER}{'='*50}")
    print(f"  RESULTS: {results['passed']}/{total} passed, {results['failed']} failed")
    print(f"{'='*50}{RESET}")
    if results["failed"] > 0:
        print(f"  {FAIL} Some tests failed!")
        return 1
    else:
        print(f"  {PASS} All tests passed!")
        return 0


async def main():
    parser = argparse.ArgumentParser(description="Manual test for Forge Phase 1")
    parser.add_argument("--pipeline", action="store_true", help="Run direct pipeline tests (mocked LLM)")
    parser.add_argument("--api", action="store_true", help="Run API endpoint tests (server must be on :8000)")
    parser.add_argument("--all", action="store_true", help="Run both pipeline and API tests")
    args = parser.parse_args()

    if not (args.pipeline or args.api or args.all):
        args.all = True  # Default to all

    if args.pipeline or args.all:
        print(f"\n{HEADER}{'='*50}")
        print("  PART 1: DIRECT PIPELINE TESTS (Mocked LLM)")
        print(f"{'='*50}{RESET}")
        await test_pipeline()

    if args.api or args.all:
        print(f"\n{HEADER}{'='*50}")
        print("  PART 2: API ENDPOINT TESTS (Live Server)")
        print(f"{'='*50}{RESET}")
        try:
            await test_api()
        except Exception as e:
            if "connect" in str(e).lower():
                print(f"  {FAIL} Cannot connect to server on :8000. Is it running?")
                print(f"  {INFO} Start with: uv run api.py")
                results["failed"] += 1
            else:
                raise

    return print_summary()


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
