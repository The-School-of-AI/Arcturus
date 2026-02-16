
import unittest
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.previews import get_preview

class TestPreviews(unittest.TestCase):
    def test_file_previews(self):
        # 1. Test Markdown
        md_file = "test_preview.md"
        Path(md_file).write_text("# Hello World")
        resp = get_preview(md_file)
        self.assertEqual(resp.viewer, "markdown")
        self.assertEqual(resp.content, "# Hello World")
        os.remove(md_file)
        
        # 2. Test JSON (DAG)
        dag_file = "test_dag.json"
        dag_data = {"nodes": [], "links": []}
        Path(dag_file).write_text(json.dumps(dag_data))
        resp = get_preview(dag_file)
        self.assertEqual(resp.viewer, "dag")
        os.remove(dag_file)
        
        # 3. Test Binary (PDF)
        pdf_file = "test.pdf"
        Path(pdf_file).write_bytes(b"%PDF-1.4")
        resp = get_preview(pdf_file)
        self.assertEqual(resp.viewer, "pdf")
        self.assertTrue(resp.url.startswith("/rag/document_content"))
        os.remove(pdf_file)

    def test_routing_guarantee(self):
        # Test unknown extension
        unknown_file = "test.xyz_abc"
        Path(unknown_file).write_text("mysterious content")
        with self.assertLogs(level='WARNING') as cm:
            resp = get_preview(unknown_file)
            self.assertEqual(resp.viewer, "code")
            self.assertTrue(any("No specific viewer found" in log for log in cm.output))
        os.remove(unknown_file)

    def test_url_previews(self):
        # 1. Test Web
        resp = get_preview("https://google.com")
        self.assertEqual(resp.viewer, "web")
        
        # 2. Test PDF URL
        resp = get_preview("https://arxiv.org/pdf/2301.12345.pdf")
        self.assertEqual(resp.viewer, "pdf")

if __name__ == "__main__":
    unittest.main()
