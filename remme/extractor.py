"""
REMME Extractor - Extracts memories AND raw preferences from conversations.

This module handles the LLM-based extraction that produces:
1. Memory commands (add/update/delete) for the FAISS store
2. Raw preferences → Staging queue (normalized later by Normalizer)

The extractor uses free-form extraction - it doesn't need to know the hub schema.
"""

import requests
import json
import sys
from typing import List, Dict, Tuple, Optional
from pathlib import Path

# Add project root to path and import settings
sys.path.insert(0, str(Path(__file__).parent.parent))
from config.settings_loader import settings, get_ollama_url, get_model, get_timeout


class RemmeExtractor:
    """
    Extracts memories and structured preferences from conversations.
    """
    
    def __init__(self, model: str = None):
        # Use provided model or default from settings
        self.model = model or get_model("memory_extraction")
        self.api_url = get_ollama_url("chat")

    def extract(
        self,
        query: str,
        conversation_history: List[Dict],
        existing_memories: List[Dict] = None
    ) -> Tuple[List[Dict], Dict]:
        """
        Extract memories and preferences from conversation.
        
        Returns:
            Tuple of (memory_commands, preferences_dict)
            - memory_commands: [{"action": "add", "text": "..."}, ...]
            - preferences_dict: {"dietary_style": "vegetarian", ...}
        """
        
        # 1. Format history into a readable transcript
        transcript = ""
        for msg in conversation_history[-5:]:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            transcript += f"{role.upper()}: {content}\n"
        
        # Add current query
        transcript += f"USER: {query}\n"
        
        # Format existing memories for the prompt
        memories_str = "NONE"
        if existing_memories:
            memories_str = "\n".join([f"ID: {m['id']} | Fact: {m['text']}" for m in existing_memories])

        # 2. Load extraction prompt
        try:
            prompt_path = Path(__file__).parent.parent / "prompts" / "remme_extraction.md"
            base_prompt = prompt_path.read_text().strip()
        except:
            base_prompt = settings.get("remme", {}).get("extraction_prompt", "Extract facts from conversation.")

        system_prompt = f"""{base_prompt}

EXISTING RELEVANT MEMORIES:
{memories_str}
"""

        print(f"[DEBUG] RemMe Target Model: {self.model}")
        
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": f"Conversation:\n{transcript}\n\nExtract memories and preferences:"}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.1},
                    "format": "json"
                },
                timeout=get_timeout()
            )
            response.raise_for_status()
            result = response.json()
            content = result.get("message", {}).get("content", "{}")
            print(f"[DEBUG] Raw Extraction Output ({len(content)} chars): {content[:200]}...")
            
            # Parse JSON
            return self._parse_extraction_result(content)
            
        except requests.exceptions.RequestException as e:
            print(f"[ERROR] Ollama Request Failed: {e}")
            return [], {}
        except Exception as e:
            print(f"[ERROR] RemMe Extraction Unexpected Error: {e}")
            return [], {}

    def _parse_extraction_result(self, content: str) -> Tuple[List[Dict], Dict]:
        """
        Parse the LLM output into memory commands and preferences.
        
        Handles multiple formats:
        - New format: {"memories": [...], "preferences": {...}}
        - Legacy format: [{"action": "add", ...}]
        """
        try:
            parsed = json.loads(content)
            
            memories = []
            preferences = {}
            
            # New dual-output format
            if isinstance(parsed, dict):
                # Extract memories
                if "memories" in parsed:
                    for item in parsed["memories"]:
                        if isinstance(item, dict) and "action" in item:
                            memories.append(item)
                
                # Extract preferences
                if "preferences" in parsed:
                    preferences = parsed["preferences"] or {}
                
                # Legacy: handle "commands" key
                elif "commands" in parsed:
                    for item in parsed["commands"]:
                        if isinstance(item, dict) and "action" in item:
                            memories.append(item)
                
                # Legacy: single action object
                elif "action" in parsed:
                    memories = [parsed]
            
            # Legacy: list of commands
            elif isinstance(parsed, list):
                for item in parsed:
                    if isinstance(item, dict) and "action" in item:
                        memories.append(item)
                    elif isinstance(item, str):
                        memories.append({"action": "add", "text": item})
            
            print(f"[DEBUG] Parsed {len(memories)} memories, {len(preferences)} preferences.")
            return memories, preferences
            
        except json.JSONDecodeError:
            print(f"[WARN] Failed to parse JSON from RemMe: {content[:100]}...")
            return [], {}

    def extract_legacy(
        self,
        query: str,
        conversation_history: List[Dict],
        existing_memories: List[Dict] = None
    ) -> List[Dict]:
        """
        Legacy method that returns only memory commands (for backward compatibility).
        """
        memories, _ = self.extract(query, conversation_history, existing_memories)
        return memories


def apply_preferences_to_hubs(preferences: Dict) -> List[str]:
    """
    Apply extracted preferences to REMME hubs.
    
    Args:
        preferences: Dict of preference key-value pairs from extraction
        
    Returns:
        List of changes made (for logging)
    """
    from remme.hubs import get_preferences_hub, get_operating_context_hub, get_soft_identity_hub
    from remme.engines import get_evidence_log
    
    prefs_hub = get_preferences_hub()
    context_hub = get_operating_context_hub()
    soft_hub = get_soft_identity_hub()
    evidence_log = get_evidence_log()
    
    changes = []
    
    # === OUTPUT CONTRACT ===
    if preferences.get("verbosity"):
        prefs_hub.set_verbosity(preferences["verbosity"])
        changes.append(f"verbosity={preferences['verbosity']}")
    
    if preferences.get("format"):
        prefs_hub.set_format(preferences["format"])
        changes.append(f"format={preferences['format']}")
    
    for tone in (preferences.get("tone") or []):
        if tone:
            prefs_hub.add_tone_constraint(tone)
            changes.append(f"tone={tone}")
    
    # === TECHNICAL CONTEXT ===
    for lang in (preferences.get("primary_languages") or []):
        if lang:
            context_hub.add_primary_language(lang, "extraction")
            changes.append(f"language={lang}")
    
    if preferences.get("package_manager_python"):
        context_hub.set_package_manager("python", preferences["package_manager_python"], "extraction")
        changes.append(f"pm_python={preferences['package_manager_python']}")
    
    if preferences.get("package_manager_js"):
        context_hub.set_package_manager("javascript", preferences["package_manager_js"], "extraction")
        changes.append(f"pm_js={preferences['package_manager_js']}")
    
    for fw in (preferences.get("frameworks_frontend") or []):
        if fw:
            prefs_hub.add_framework("frontend", fw)
            changes.append(f"frontend={fw}")
    
    for fw in (preferences.get("frameworks_backend") or []):
        if fw:
            prefs_hub.add_framework("backend", fw)
            changes.append(f"backend={fw}")
    
    for test in (preferences.get("testing") or []):
        if test:
            prefs_hub.data.tooling_defaults.testing.append(test)
            changes.append(f"testing={test}")
    
    # === SOFT IDENTITY ===
    if preferences.get("dietary_style"):
        soft_hub.set_dietary_style(preferences["dietary_style"])
        changes.append(f"diet={preferences['dietary_style']}")
    
    for cuisine in (preferences.get("cuisine_likes") or []):
        if cuisine:
            soft_hub.add_cuisine_like(cuisine)
            changes.append(f"cuisine_like={cuisine}")
    
    for cuisine in (preferences.get("cuisine_dislikes") or []):
        if cuisine:
            soft_hub.add_cuisine_dislike(cuisine)
            changes.append(f"cuisine_dislike={cuisine}")
    
    for food in (preferences.get("favorite_foods") or []):
        if food:
            soft_hub.data.food_and_dining.cuisine_affinities.favorites.append(food)
            changes.append(f"fav_food={food}")
    
    if preferences.get("pet_affinity"):
        soft_hub.set_pet_affinity(preferences["pet_affinity"])
        changes.append(f"pet={preferences['pet_affinity']}")
    
    for name in (preferences.get("pet_names") or []):
        if name:
            soft_hub.data.pets_and_animals.ownership.pet_names.append(name)
            changes.append(f"pet_name={name}")
    
    for genre in (preferences.get("music_genres") or []):
        if genre:
            soft_hub.add_music_genre(genre)
            changes.append(f"music={genre}")
    
    for genre in (preferences.get("movie_genres") or []):
        if genre:
            soft_hub.data.media_and_entertainment.movies_tv.genres.append(genre)
            changes.append(f"movie={genre}")
    
    for hobby in (preferences.get("hobbies") or []):
        if hobby:
            soft_hub.add_hobby(hobby)
            changes.append(f"hobby={hobby}")
    
    for interest in (preferences.get("professional_interests") or []):
        if interest:
            soft_hub.add_professional_interest(interest)
            changes.append(f"pro_interest={interest}")
    
    for interest in (preferences.get("learning_interests") or []):
        if interest:
            soft_hub.data.interests_and_hobbies.learning_interests.append(interest)
            changes.append(f"learning={interest}")
    
    if preferences.get("humor_tolerance"):
        soft_hub.set_humor_tolerance(preferences["humor_tolerance"])
        changes.append(f"humor={preferences['humor_tolerance']}")
    
    if preferences.get("small_talk_tolerance"):
        soft_hub.set_small_talk_tolerance(preferences["small_talk_tolerance"])
        changes.append(f"small_talk={preferences['small_talk_tolerance']}")
    
    if preferences.get("experience_level"):
        soft_hub.set_experience_level(preferences["experience_level"])
        changes.append(f"experience={preferences['experience_level']}")
    
    if preferences.get("industry"):
        soft_hub.data.professional_context.industry.value = preferences["industry"]
        changes.append(f"industry={preferences['industry']}")
    
    if preferences.get("role_type"):
        soft_hub.data.professional_context.role_type.value = preferences["role_type"]
        changes.append(f"role={preferences['role_type']}")
    
    if preferences.get("location"):
        context_hub.data.environment.location_region.value = preferences["location"]
        changes.append(f"location={preferences['location']}")
    
    # Log evidence if changes were made
    if changes:
        evidence_log.add_event(
            source_type="conversation",
            source_reference="remme_extraction",
            signal_category="explicit_preference",
            raw_excerpt=f"Extracted {len(changes)} preferences",
            derived_updates=[{"target_hub": "all", "operation": "set", "new_value": changes}],
            confidence_impact=0.2
        )
        
        # Save all hubs
        prefs_hub.save()
        context_hub.save()
        soft_hub.save()
        evidence_log.save()
        
        print(f"✅ Applied {len(changes)} preference changes to hubs")
    
    return changes
