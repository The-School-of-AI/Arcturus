"""
Memory Bootstrap Extractor - Populates UserModel hubs from existing REMME memories.

Uses LLM to extract structured preferences from unstructured memory snippets.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings_loader import get_model
from core.model_manager import ModelManager


EXTRACTION_PROMPT = """You are extracting structured user preferences from memory snippets.

MEMORIES:
{memories}

---

Extract ALL relevant information into the following JSON structure. Use null for unknown fields.
Be thorough - extract every piece of information that can be inferred.

{{
  "preferences": {{
    "verbosity": "concise|detailed|balanced",
    "format": "markdown|plain|code_heavy",
    "tone_constraints": ["no_fluff", "professional", etc],
    "avoid_phrases": ["phrases user dislikes"],
    "avoid_moves": ["behaviors user dislikes"],
    "package_manager_python": "uv|pip|poetry|conda",
    "package_manager_js": "pnpm|npm|yarn|bun",
    "frontend_frameworks": ["react", "vue", etc],
    "backend_frameworks": ["fastapi", "django", etc],
    "testing_frameworks": ["pytest", "jest", etc],
    "preferred_libraries": {{"purpose": "library_name"}}
  }},
  "operating_context": {{
    "primary_languages": ["python", "typescript", etc],
    "editor_ide": "vscode|cursor|vim|etc",
    "cloud_providers": ["gcp", "aws", "azure"],
    "databases": ["postgres", "mongodb", etc],
    "location": "city or region if mentioned"
  }},
  "soft_identity": {{
    "dietary_style": "vegetarian|vegan|non-vegetarian|etc",
    "cuisine_likes": ["cuisines user likes"],
    "cuisine_dislikes": ["cuisines user dislikes"],
    "favorite_foods": ["specific favorite foods/dishes"],
    "food_allergies": ["allergies if mentioned"],
    "pet_affinity": "dog|cat|both|other|none",
    "pet_names": ["names of their pets"],
    "music_genres": ["liked music genres"],
    "movie_genres": ["liked movie/TV genres"],
    "book_genres": ["liked book genres"],
    "favorite_artists": ["music artists"],
    "favorite_movies": ["specific movies/shows"],
    "favorite_books": ["specific books/authors"],
    "hobbies": ["hobbies and activities"],
    "sports_interests": ["sports they follow or play"],
    "professional_interests": ["professional/tech interests"],
    "learning_interests": ["topics they want to learn"],
    "industry": "tech|education|finance|etc",
    "role_type": "engineer|teacher|founder|etc",
    "experience_level": "junior|mid|senior|expert",
    "company_or_org": "where they work/teach",
    "humor_tolerance": "high|medium|low|none",
    "small_talk_tolerance": "high|medium|low|none",
    "activity_level": "active|moderate|sedentary",
    "favorite_colors": ["colors if mentioned"],
    "travel_preferences": ["travel style or destinations"],
    "personality_traits": ["traits that come through"]
  }}
}}

IMPORTANT:
- Extract EVERYTHING that can be inferred
- Use exact words from memories when possible
- Include partial information (better than nothing)
- For lists, include all items mentioned across all memories

Return ONLY valid JSON, no explanation."""


async def extract_from_memories(memories: List[Dict]) -> Dict[str, Any]:
    """
    Extract structured preferences from REMME memories using LLM.
    
    Args:
        memories: List of memory dicts with 'text' and 'category' fields
    
    Returns:
        Extracted preferences dict
    """
    if not memories:
        return {}
    
    # Format memories for prompt
    memory_text = "\n".join([
        f"- {m.get('text', '')} [Category: {m.get('category', 'general')}]"
        for m in memories
    ])
    
    prompt = EXTRACTION_PROMPT.format(memories=memory_text)
    
    # Use extraction model
    model_name = get_model("memory_extraction")
    model = ModelManager(model_name, provider="ollama")
    
    try:
        response = await model.generate_text(prompt)
        
        # Parse JSON from response
        # Try to extract JSON from response
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            return json.loads(json_str)
    except Exception as e:
        print(f"❌ Extraction failed: {e}")
    
    return {}


def apply_extraction_to_hubs(extraction: Dict[str, Any]):
    """
    Apply extracted data to UserModel hubs.
    
    Args:
        extraction: Dict with 'preferences', 'operating_context', 'soft_identity' keys
    """
    from remme.hubs.preferences_hub import get_preferences_hub
    from remme.hubs.operating_context_hub import get_operating_context_hub
    from remme.hubs.soft_identity_hub import get_soft_identity_hub
    from remme.engines.evidence_log import get_evidence_log
    
    prefs_hub = get_preferences_hub()
    context_hub = get_operating_context_hub()
    soft_hub = get_soft_identity_hub()
    evidence_log = get_evidence_log()
    
    changes_made = []
    
    # === PREFERENCES ===
    prefs = extraction.get("preferences", {})
    
    if prefs.get("verbosity"):
        prefs_hub.set_verbosity(prefs["verbosity"])
        changes_made.append(f"verbosity={prefs['verbosity']}")
    
    if prefs.get("format"):
        prefs_hub.set_format(prefs["format"])
        changes_made.append(f"format={prefs['format']}")
    
    for constraint in prefs.get("tone_constraints", []):
        if constraint:
            prefs_hub.add_tone_constraint(constraint)
            changes_made.append(f"tone={constraint}")
    
    for phrase in prefs.get("avoid_phrases", []):
        if phrase:
            prefs_hub.add_avoid_phrase(phrase)
            changes_made.append(f"avoid_phrase={phrase}")
    
    if prefs.get("package_manager_python"):
        context_hub.set_package_manager("python", prefs["package_manager_python"], "memory_extraction")
        changes_made.append(f"pm_python={prefs['package_manager_python']}")
    
    if prefs.get("package_manager_js"):
        context_hub.set_package_manager("javascript", prefs["package_manager_js"], "memory_extraction")
        changes_made.append(f"pm_js={prefs['package_manager_js']}")
    
    for fw in prefs.get("frontend_frameworks", []):
        if fw:
            prefs_hub.add_framework("frontend", fw)
            changes_made.append(f"frontend_fw={fw}")
    
    for fw in prefs.get("backend_frameworks", []):
        if fw:
            prefs_hub.add_framework("backend", fw)
            changes_made.append(f"backend_fw={fw}")
    
    # === OPERATING CONTEXT ===
    ctx = extraction.get("operating_context", {})
    
    for lang in ctx.get("primary_languages", []):
        if lang:
            context_hub.add_primary_language(lang, "memory_extraction")
            changes_made.append(f"language={lang}")
    
    if ctx.get("location"):
        context_hub.data.environment.location_region.value = ctx["location"]
        context_hub.data.environment.location_region.confidence = 0.6
        context_hub.data.environment.location_region.last_seen_at = datetime.now()
        changes_made.append(f"location={ctx['location']}")
    
    # === SOFT IDENTITY ===
    soft = extraction.get("soft_identity", {})
    
    if soft.get("dietary_style"):
        soft_hub.set_dietary_style(soft["dietary_style"])
        changes_made.append(f"diet={soft['dietary_style']}")
    
    for cuisine in soft.get("cuisine_likes", []):
        if cuisine:
            soft_hub.add_cuisine_like(cuisine)
            changes_made.append(f"cuisine_like={cuisine}")
    
    for cuisine in soft.get("cuisine_dislikes", []):
        if cuisine:
            soft_hub.add_cuisine_dislike(cuisine)
            changes_made.append(f"cuisine_dislike={cuisine}")
    
    for food in soft.get("favorite_foods", []):
        if food:
            soft_hub.data.food_and_dining.cuisine_affinities.favorites.append(food)
            changes_made.append(f"fav_food={food}")
    
    if soft.get("pet_affinity"):
        soft_hub.set_pet_affinity(soft["pet_affinity"])
        changes_made.append(f"pet={soft['pet_affinity']}")
    
    for name in soft.get("pet_names", []):
        if name:
            soft_hub.data.pets_and_animals.ownership.pet_names.append(name)
            changes_made.append(f"pet_name={name}")
    
    for genre in soft.get("music_genres", []):
        if genre:
            soft_hub.add_music_genre(genre)
            changes_made.append(f"music={genre}")
    
    for genre in soft.get("movie_genres", []):
        if genre:
            soft_hub.data.media_and_entertainment.movies_tv.genres.append(genre)
            changes_made.append(f"movie_genre={genre}")
    
    for genre in soft.get("book_genres", []):
        if genre:
            soft_hub.data.media_and_entertainment.books.genres.append(genre)
            changes_made.append(f"book_genre={genre}")
    
    for hobby in soft.get("hobbies", []):
        if hobby:
            soft_hub.add_hobby(hobby)
            changes_made.append(f"hobby={hobby}")
    
    for interest in soft.get("professional_interests", []):
        if interest:
            soft_hub.add_professional_interest(interest)
            changes_made.append(f"pro_interest={interest}")
    
    for interest in soft.get("learning_interests", []):
        if interest:
            soft_hub.data.interests_and_hobbies.learning_interests.append(interest)
            changes_made.append(f"learning={interest}")
    
    if soft.get("industry"):
        soft_hub.data.professional_context.industry.value = soft["industry"]
        soft_hub.data.professional_context.industry.confidence = 0.6
        changes_made.append(f"industry={soft['industry']}")
    
    if soft.get("role_type"):
        soft_hub.data.professional_context.role_type.value = soft["role_type"]
        soft_hub.data.professional_context.role_type.confidence = 0.6
        changes_made.append(f"role={soft['role_type']}")
    
    if soft.get("experience_level"):
        soft_hub.set_experience_level(soft["experience_level"])
        changes_made.append(f"exp_level={soft['experience_level']}")
    
    if soft.get("company_or_org"):
        soft_hub.data.professional_context.team_size.value = soft["company_or_org"]
        changes_made.append(f"company={soft['company_or_org']}")
    
    if soft.get("humor_tolerance"):
        soft_hub.set_humor_tolerance(soft["humor_tolerance"])
        changes_made.append(f"humor={soft['humor_tolerance']}")
    
    if soft.get("small_talk_tolerance"):
        soft_hub.set_small_talk_tolerance(soft["small_talk_tolerance"])
        changes_made.append(f"small_talk={soft['small_talk_tolerance']}")
    
    if soft.get("activity_level"):
        soft_hub.data.lifestyle_and_wellness.activity_level.value = soft["activity_level"]
        soft_hub.data.lifestyle_and_wellness.activity_level.confidence = 0.5
        changes_made.append(f"activity={soft['activity_level']}")
    
    # Log evidence
    if changes_made:
        evidence_log.add_event(
            source_type="memory_bootstrap",
            source_reference="remme_memories",
            signal_category="system_observation",
            raw_excerpt=f"Bootstrapped from {len(changes_made)} extracted fields",
            derived_updates=[
                {
                    "target_hub": "all",
                    "target_path": "bootstrap",
                    "operation": "set",
                    "new_value": changes_made
                }
            ],
            confidence_impact=0.3
        )
    
    # Save all hubs
    prefs_hub.save()
    context_hub.save()
    soft_hub.save()
    evidence_log.save()
    
    print(f"✅ Bootstrap applied {len(changes_made)} changes to hubs")
    return changes_made


async def bootstrap_from_remme():
    """
    Main entry point: Load REMME memories and bootstrap UserModel hubs.
    """
    from shared.state import get_remme_store
    
    print("🚀 Starting UserModel bootstrap from REMME memories...")
    
    store = get_remme_store()
    if not store.index:
        store.load_index()
    
    memories = store.get_all()
    
    if not memories:
        print("⚠️ No memories found to bootstrap from")
        return []
    
    print(f"📚 Found {len(memories)} memories to analyze")
    
    # Extract structured data
    extraction = await extract_from_memories(memories)
    
    if not extraction:
        print("⚠️ Extraction returned empty results")
        return []
    
    # Apply to hubs
    changes = apply_extraction_to_hubs(extraction)
    
    return changes
