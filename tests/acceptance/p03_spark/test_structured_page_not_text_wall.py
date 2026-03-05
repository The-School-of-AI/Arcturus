import asyncio
import json
import os
from pathlib import Path

import pytest

from content import page_generator


def _gen(query: str):
    return asyncio.get_event_loop().run_until_complete(page_generator.generate_page(query, template="topic_overview", created_by="test"))


def test_generate_page_happy_path_returns_structure():
    page = _gen("electric scooters 2026")
    assert isinstance(page, dict)
    assert page.get("id")
    assert "sections" in page


def test_generated_page_has_at_least_two_sections():
    page = _gen("market analysis")
    assert len(page.get("sections", [])) >= 2


def test_generated_page_contains_data_block_or_table_anchor():
    page = _gen("data query")
    found = False
    for s in page.get("sections", []):
        for b in s.get("blocks", []):
            if b.get("kind") == "table":
                found = True
    assert found, "Expected at least one table block in sections"


def test_generated_page_has_citation_anchors():
    page = _gen("citations query")
    citations = page.get("citations", {})
    # some citation ids expected
    assert isinstance(citations, dict)
    # ensure that at least one section references a citation id that exists in page.citations
    any_ref = False
    for s in page.get("sections", []):
        for b in s.get("blocks", []):
            if b.get("kind") == "citation" and b.get("ids"):
                for cid in b.get("ids"):
                    if cid in citations:
                        any_ref = True
    assert any_ref, "No citation anchors found linking to page.citations"


def test_invalid_payload_raises():
    with pytest.raises(ValueError):
        asyncio.get_event_loop().run_until_complete(page_generator.generate_page(""))


def test_persistence_saves_and_loads():
    page = _gen("persistence test query")
    pid = page.get("id")
    path = Path(page_generator.DATA_DIR) / f"{pid}.json"
    assert path.exists()
    loaded = page_generator.load_page(pid)
    assert loaded.get("id") == pid


def test_agent_idempotency_on_same_query():
    p1 = _gen("idempotency query")
    p2 = _gen("idempotency query")
    # the page ids can be different, but sections content should be deterministic for stubs
    s1 = json.dumps(p1.get("sections"), sort_keys=True)
    s2 = json.dumps(p2.get("sections"), sort_keys=True)
    assert s1 == s2


def test_concurrent_generation_requests():
    async def run_many():
        tasks = [page_generator.generate_page(f"concurrent {i}") for i in range(4)]
        res = await asyncio.gather(*tasks)
        return res

    pages = asyncio.get_event_loop().run_until_complete(run_many())
    assert len(pages) == 4
"""Acceptance scaffold for P03 (p03_spark).

Replace these contract tests with feature-level assertions as implementation matures.
"""

from pathlib import Path

PROJECT_ID = "P03"
PROJECT_KEY = "p03_spark"
CI_CHECK = "p03-spark-pages"
CHARTER = Path("CAPSTONE/project_charters/P03_spark_synthesized_content_pages_sparkpages.md")
DELIVERY_README = Path("CAPSTONE/project_charters/P03_DELIVERY_README.md")
DEMO_SCRIPT = Path("scripts/demos/p03_spark.sh")
THIS_FILE = Path("tests/acceptance/p03_spark/test_structured_page_not_text_wall.py")


def _charter_text() -> str:
    return CHARTER.read_text(encoding="utf-8")


def test_01_charter_exists() -> None:
    assert CHARTER.exists(), "Missing charter: " + str(CHARTER)


def test_02_expanded_gate_contract_present() -> None:
    assert "Expanded Mandatory Test Gate Contract (10 Hard Conditions)" in _charter_text()


def test_03_acceptance_path_declared_in_charter() -> None:
    assert THIS_FILE.as_posix() in _charter_text()


def test_04_demo_script_exists() -> None:
    assert DEMO_SCRIPT.exists(), "Missing demo script: " + str(DEMO_SCRIPT)


def test_05_demo_script_is_executable() -> None:
    assert DEMO_SCRIPT.stat().st_mode & 0o111, "Demo script not executable: " + str(DEMO_SCRIPT)


def test_06_delivery_readme_exists() -> None:
    assert DELIVERY_README.exists(), "Missing delivery README: " + str(DELIVERY_README)


def test_07_delivery_readme_has_required_sections() -> None:
    required = [
        "## 1. Scope Delivered",
        "## 2. Architecture Changes",
        "## 3. API And UI Changes",
        "## 4. Mandatory Test Gate Definition",
        "## 5. Test Evidence",
        "## 8. Known Gaps",
        "## 10. Demo Steps",
    ]
    text = DELIVERY_README.read_text(encoding="utf-8")
    for section in required:
        assert section in text, "Missing section " + section + " in " + str(DELIVERY_README)


def test_08_ci_check_declared_in_charter() -> None:
    assert CI_CHECK in _charter_text()
