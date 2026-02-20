"""Section agent package for Spark page generator.

Each agent implements a simple async `generate_section(query, page_context, resources)`
function which returns a section dict following the schema in `content/schema.md`.
These are intentionally small stubs for Phase 1.
"""

from .overview_agent import generate_section as overview_generate_section
from .detail_agent import generate_section as detail_generate_section
from .data_agent import generate_section as data_generate_section
from .source_agent import generate_section as source_generate_section

__all__ = [
    "overview_generate_section",
    "detail_generate_section",
    "data_generate_section",
    "source_generate_section",
]
