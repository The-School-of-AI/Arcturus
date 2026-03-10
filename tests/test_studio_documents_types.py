"""Tests for core/studio/documents/types.py — doc type registry and resolution."""

import pytest

from core.studio.documents.types import (
    DEFAULT_DOC_TYPE,
    DOC_TYPE_TEMPLATES,
    get_doc_type_template,
    resolve_document_type,
)


class TestDocTypeTemplates:
    def test_templates_exist(self):
        assert "technical_spec" in DOC_TYPE_TEMPLATES
        assert "report" in DOC_TYPE_TEMPLATES
        assert "proposal" in DOC_TYPE_TEMPLATES

    def test_template_has_required_sections(self):
        for doc_type, tmpl in DOC_TYPE_TEMPLATES.items():
            assert "required_sections" in tmpl, f"{doc_type} missing required_sections"
            assert len(tmpl["required_sections"]) >= 2

    def test_template_has_min_max_sections(self):
        for doc_type, tmpl in DOC_TYPE_TEMPLATES.items():
            assert tmpl["min_sections"] <= tmpl["max_sections"]

    def test_default_doc_type_exists(self):
        assert DEFAULT_DOC_TYPE in DOC_TYPE_TEMPLATES


class TestResolveDocumentType:
    def test_explicit_parameter(self):
        result = resolve_document_type({"doc_type": "technical_spec"})
        assert result == "technical_spec"

    def test_explicit_document_type_key(self):
        result = resolve_document_type({"document_type": "proposal"})
        assert result == "proposal"

    def test_keyword_from_prompt(self):
        result = resolve_document_type(None, "Create a technical specification for the API")
        assert result == "technical_spec"

    def test_keyword_report(self):
        result = resolve_document_type(None, "Write a report on quarterly findings")
        assert result == "report"

    def test_keyword_proposal(self):
        result = resolve_document_type(None, "Draft a proposal for the new project")
        assert result == "proposal"

    def test_defaults_to_report(self):
        result = resolve_document_type(None, "Write something nice")
        assert result == DEFAULT_DOC_TYPE

    def test_none_inputs(self):
        result = resolve_document_type(None, None)
        assert result == DEFAULT_DOC_TYPE

    def test_params_take_priority_over_prompt(self):
        result = resolve_document_type(
            {"doc_type": "proposal"},
            "Write a technical specification",
        )
        assert result == "proposal"

    def test_unknown_param_falls_to_prompt(self):
        result = resolve_document_type(
            {"doc_type": "unknown_type"},
            "Write a proposal",
        )
        assert result == "proposal"

    def test_unknown_param_and_no_keyword(self):
        result = resolve_document_type(
            {"doc_type": "unknown_type"},
            "Write something",
        )
        assert result == DEFAULT_DOC_TYPE


class TestGetDocTypeTemplate:
    def test_known_type(self):
        tmpl = get_doc_type_template("technical_spec")
        assert "Introduction" in tmpl["required_sections"]

    def test_unknown_falls_back_to_report(self):
        tmpl = get_doc_type_template("nonexistent")
        assert tmpl == DOC_TYPE_TEMPLATES[DEFAULT_DOC_TYPE]
