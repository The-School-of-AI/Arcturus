"""Speaker notes scoring and repair for Forge slides."""

import re
from typing import Optional

from core.schemas.studio_schema import Slide, SlidesContentTree

# Quality thresholds
_MIN_WORDS = 15
_MIN_WORDS_TITLE = 8
_MAX_WORDS = 140
_MIN_SENTENCES = 2
_MIN_SENTENCES_TITLE = 1
_COPY_THRESHOLD = 0.60
_DECK_PASS_RATE = 0.90

# Slide types with relaxed thresholds
_RELAXED_TYPES = {"title"}

# Template fillers per slide type
_TEMPLATES = {
    "title": "Welcome the audience and set the stage for the presentation. Preview the main topics to be covered.",
    "content": "Discuss the key points on this slide. Highlight the most important insight and explain its implications for the audience.",
    "two_column": "Walk through both columns and explain the relationship between the two sides. Highlight key differences or complementary aspects.",
    "comparison": "Compare and contrast the two perspectives shown. Guide the audience through the key distinctions and why they matter.",
    "timeline": "Walk through each milestone in sequence. Explain the significance of each phase and how they connect to the overall narrative.",
    "chart": "Draw attention to the key data trend. Explain what the numbers mean in practical terms and connect the insight to your core message.",
    "image_text": "Describe the visual and connect it to the narrative. Use the image as an anchor for the key point you want the audience to remember.",
    "quote": "Read the quote with emphasis. Explain why this perspective matters and how it connects to the broader argument of your presentation.",
    "code": "Walk through the code step by step. Highlight the key logic and explain why this implementation approach was chosen.",
    "team": "Introduce each team member briefly. Highlight relevant expertise and explain how the team composition supports your project goals.",
    "stat": "Highlight the key metric and explain why it matters. Connect the numbers to your core argument and give the audience context for interpretation.",
    "section_divider": "Signal the transition to a new section. Briefly preview what this section will cover and why it matters in the overall narrative.",
    "image_full": "Draw the audience's attention to the visual. Explain its significance and how it relates to the presentation's core message.",
    "agenda": "Preview the structure of the presentation. Walk through each agenda item briefly so the audience knows what to expect.",
    "table": "Walk through the key data points in the table. Highlight notable trends or outliers and explain what the data means for your argument.",
}


def _count_words(text: str) -> int:
    return len(text.split())


def _count_sentences(text: str) -> int:
    # Split on sentence-ending punctuation
    sentences = re.split(r'[.!?]+', text.strip())
    return len([s for s in sentences if s.strip()])


def _compute_overlap(notes: str, body_text: str) -> float:
    """Compute word overlap ratio between notes and body text."""
    if not notes or not body_text:
        return 0.0
    notes_words = set(notes.lower().split())
    body_words = set(body_text.lower().split())
    if not notes_words:
        return 0.0
    overlap = notes_words & body_words
    return len(overlap) / len(notes_words)


def _get_slide_body_text(slide: Slide) -> str:
    """Extract body/bullet/stat text from slide elements."""
    texts = []
    for el in slide.elements:
        if el.type in ("body", "bullet_list", "title", "subtitle", "stat_callout"):
            if isinstance(el.content, list):
                for item in el.content:
                    if isinstance(item, dict):
                        texts.extend(str(v) for v in item.values())
                    else:
                        texts.append(str(item))
            elif el.content:
                texts.append(str(el.content))
    return " ".join(texts)


def _is_title_or_closing(slide: Slide, index: int = 0, total: int = 1) -> bool:
    """Check if slide is a title or closing slide."""
    if slide.slide_type in _RELAXED_TYPES:
        return True
    # Last slide is often a closing
    if index == total - 1 and slide.slide_type == "title":
        return True
    return False


def score_speaker_notes(slide: Slide, index: int = 0, total: int = 1) -> dict:
    """Score the quality of a single slide's speaker notes.

    Returns dict with word_count, sentence_count, is_empty, is_too_short,
    is_too_long, is_copy, passes.
    """
    notes = (slide.speaker_notes or "").strip()
    body_text = _get_slide_body_text(slide)

    word_count = _count_words(notes) if notes else 0
    sentence_count = _count_sentences(notes) if notes else 0
    is_empty = not notes
    overlap = _compute_overlap(notes, body_text)

    relaxed = _is_title_or_closing(slide, index, total)
    min_words = _MIN_WORDS_TITLE if relaxed else _MIN_WORDS
    min_sentences = _MIN_SENTENCES_TITLE if relaxed else _MIN_SENTENCES

    is_too_short = word_count < min_words and not is_empty
    is_too_long = word_count > _MAX_WORDS
    is_copy = overlap > _COPY_THRESHOLD

    passes = (
        not is_empty
        and not is_too_short
        and not is_too_long
        and not is_copy
        and word_count >= min_words
        and sentence_count >= min_sentences
    )

    return {
        "word_count": word_count,
        "sentence_count": sentence_count,
        "is_empty": is_empty,
        "is_too_short": is_too_short,
        "is_too_long": is_too_long,
        "is_copy": is_copy,
        "passes": passes,
    }


def repair_speaker_notes(content_tree: SlidesContentTree) -> SlidesContentTree:
    """Post-generation repair pass for speaker notes.

    Returns a new SlidesContentTree (does not mutate the input).
    """
    total = len(content_tree.slides)
    new_slides = []

    for i, slide in enumerate(content_tree.slides):
        score = score_speaker_notes(slide, i, total)
        notes = (slide.speaker_notes or "").strip()
        relaxed = _is_title_or_closing(slide, i, total)

        if score["is_empty"]:
            # Generate template filler
            notes = _get_template(slide)
        elif score["is_copy"]:
            # Replace with reframed version
            notes = _get_template(slide)
        elif score["is_too_short"]:
            # Expand with context sentences to meet minimum word count
            context = f"Elaborate on the key message of this slide about {slide.title or 'the topic'}. Connect this point to the broader narrative for the audience."
            notes = f"{notes} {context}"

        # Create new slide with repaired notes
        new_slides.append(Slide(
            id=slide.id,
            slide_type=slide.slide_type,
            title=slide.title,
            elements=slide.elements,
            speaker_notes=notes,
            metadata=slide.metadata,
        ))

    return SlidesContentTree(
        deck_title=content_tree.deck_title,
        subtitle=content_tree.subtitle,
        slides=new_slides,
        metadata=content_tree.metadata,
    )


def _get_template(slide: Slide) -> str:
    """Get template filler for a slide based on its type."""
    base = _TEMPLATES.get(slide.slide_type, _TEMPLATES["content"])
    if slide.title:
        return f"{base} This slide covers: {slide.title}."
    return base
