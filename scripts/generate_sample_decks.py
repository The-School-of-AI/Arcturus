"""Generate sample PPTX decks for visual inspection of theme/typography changes."""

from pathlib import Path
from core.schemas.studio_schema import Slide, SlideElement, SlidesContentTree
from core.studio.slides.exporter import export_to_pptx
from core.studio.slides.themes import get_theme

SAMPLE_THEMES = [
    "corporate-blue", "tech-dark", "sunset-amber", "creative-coral",
    "nature-green", "finance-navy", "executive-charcoal",
]

def _build_sample_tree() -> SlidesContentTree:
    """Build a content tree exercising multiple slide types."""
    slides = [
        # 1. Title slide
        Slide(
            id="s1",
            slide_type="title",
            title="Visual Polish Demo Deck",
            elements=[
                SlideElement(id="e1", type="subtitle", content="Color themes & typography overhaul"),
                SlideElement(id="e1b", type="badge", content="Q1 2026  |  Forge Studio  |  v2.0"),
            ],
        ),
        # 2. Section divider
        Slide(
            id="s2",
            slide_type="section_divider",
            title="Key Findings",
            elements=[
                SlideElement(id="e2", type="subtitle", content="What the data tells us"),
            ],
        ),
        # 3. Content slide with kicker + bullets + takeaway
        Slide(
            id="s3",
            slide_type="content",
            title="Market Opportunity Analysis",
            elements=[
                SlideElement(id="e3k", type="kicker", content="Industry Insights"),
                SlideElement(id="e3", type="bullet_list", content=[
                    "Global TAM expanded to **$4.2B** in 2025, up 18% YoY",
                    "Enterprise segment drives *62%* of revenue growth",
                    "Customer acquisition cost dropped by 23% with new funnel",
                    "Net retention rate at **128%** — best in class",
                ]),
                SlideElement(id="e3t", type="takeaway", content="The market is ready for disruption — act now."),
            ],
        ),
        # 4. Two-column slide
        Slide(
            id="s4",
            slide_type="two_column",
            title="Before vs. After Comparison",
            elements=[
                SlideElement(id="e4k", type="kicker", content="Design System"),
                SlideElement(id="e4a", type="bullet_list", content=[
                    "Saturated neon palettes",
                    "1.15 line spacing — cramped",
                    "Same fonts for heading/body",
                    "Plain white backgrounds",
                ]),
                SlideElement(id="e4b", type="bullet_list", content=[
                    "Desaturated, harmonious palettes",
                    "1.40 line spacing — breathable",
                    "Distinct font pairs per theme",
                    "Hue-tinted subtle backgrounds",
                ]),
            ],
        ),
        # 5. Quote slide
        Slide(
            id="s5",
            slide_type="quote",
            title="Design Philosophy",
            elements=[
                SlideElement(id="e5", type="quote", content="Good design is as little design as possible."),
                SlideElement(id="e5a", type="body", content="Dieter Rams"),
            ],
        ),
        # 6. Stats slide
        Slide(
            id="s6",
            slide_type="stat",
            title="Performance Metrics",
            elements=[
                SlideElement(id="e6k", type="kicker", content="Key Numbers"),
                SlideElement(id="e6a", type="stat_callout", content=[
                    {"value": "98.7%", "label": "Uptime SLA"},
                    {"value": "<2ms", "label": "P99 Latency"},
                    {"value": "4.2M", "label": "Daily Active Users"},
                ]),
            ],
        ),
        # 7. Timeline slide
        Slide(
            id="s7",
            slide_type="timeline",
            title="Product Roadmap 2026",
            elements=[
                SlideElement(id="e7", type="bullet_list", content=[
                    "Q1 | Theme Overhaul | Ship new color palettes and typography",
                    "Q2 | Animation Engine | Add slide transitions and micro-animations",
                    "Q3 | Collaboration | Real-time multi-user editing",
                    "Q4 | AI Copilot | Intelligent layout suggestions",
                ]),
            ],
        ),
        # 8. Content slide with body text
        Slide(
            id="s8",
            slide_type="content",
            title="Typography Details",
            elements=[
                SlideElement(id="e8k", type="kicker", content="Design Tokens"),
                SlideElement(id="e8", type="body", content=(
                    "The updated type scale uses **44pt titles**, **32pt headings**, "
                    "and **18pt body text** with 1.40× line spacing. Paragraph spacing "
                    "increased to 10pt for content and 12pt between bullets. "
                    "Kicker text is now 14pt with 120cpi letter-spacing for "
                    "a refined uppercase treatment."
                )),
            ],
        ),
        # 9. Code slide
        Slide(
            id="s9",
            slide_type="code",
            title="Implementation Example",
            elements=[
                SlideElement(id="e9", type="code", content=(
                    "def _tint_background(base_bg, tint_source, strength=0.06):\n"
                    "    \"\"\"Subtly tint a background toward a source hue.\"\"\"\n"
                    "    return _blend_color(tint_source, base_bg, strength)\n"
                )),
            ],
        ),
        # 10. Closing title
        Slide(
            id="s10",
            slide_type="title",
            title="Thank You",
            elements=[
                SlideElement(id="e10", type="subtitle", content="Questions? Let's discuss."),
            ],
        ),
    ]
    return SlidesContentTree(
        deck_title="Visual Polish Demo",
        subtitle="Theme & Typography Overhaul",
        slides=slides,
    )


def main():
    out_dir = Path("output/sample_decks")
    out_dir.mkdir(parents=True, exist_ok=True)
    tree = _build_sample_tree()

    for theme_id in SAMPLE_THEMES:
        theme = get_theme(theme_id)
        out_path = out_dir / f"demo_{theme_id}.pptx"
        export_to_pptx(tree, theme, out_path)
        print(f"  {out_path}")

    print(f"\nDone — {len(SAMPLE_THEMES)} decks in {out_dir}/")


if __name__ == "__main__":
    main()
