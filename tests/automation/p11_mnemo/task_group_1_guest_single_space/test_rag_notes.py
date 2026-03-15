"""
TG1 — RAG and Notes CRUD. Create file, list, delete.
"""

import pytest

from tests.automation.p11_mnemo.conftest import requires_qdrant_neo4j

pytestmark = [
    pytest.mark.p11_automation,
    pytest.mark.integration,
]


@requires_qdrant_neo4j
def test_tg1_rag_01_list_documents(client):
    """TG1-09: List RAG documents."""
    res = client.get("/api/rag/documents")
    assert res.status_code == 200, res.text
    body = res.json()
    assert "files" in body
    assert isinstance(body["files"], list)


@requires_qdrant_neo4j
def test_tg1_rag_02_create_and_delete_file(client):
    """TG1-09/10: Create RAG file, then delete."""
    path = "Notes/__global__/automation_test_note.txt"
    content = "Automation test note for P11."
    create_res = client.post(
        "/api/rag/create_file",
        data={"path": path, "content": content},
    )
    assert create_res.status_code == 200, create_res.text
    assert create_res.json().get("status") == "success"

    # List should include it
    list_res = client.get("/api/rag/documents")
    assert list_res.status_code == 200
    files = list_res.json().get("files", [])
    def _has_path(items, target):
        for item in items:
            if item.get("path") == target or item.get("name") == target.split("/")[-1]:
                return True
            if item.get("children"):
                if _has_path(item["children"], target):
                    return True
        return False
    assert _has_path(files, path) or path in str(files)

    # Delete
    del_res = client.post("/api/rag/delete", data={"path": path})
    assert del_res.status_code == 200, del_res.text
    assert del_res.json().get("status") == "success"
