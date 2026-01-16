"""
REMME Normalizer - LLM-based preference normalization and schema mapping.

The normalizer reads raw extracted preferences from staging and:
1. Maps them to known hub schema fields
2. Creates new fields in 'extras' for unknown concepts
3. Detects reinforcements and conflicts
4. Applies via BeliefUpdateEngine
"""

import json
import requests
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from config.settings_loader import get_model, get_ollama_url, get_timeout
from remme.staging import get_staging_store
from remme.engines.belief_update import get_belief_engine
from remme.hubs import get_preferences_hub, get_operating_context_hub, get_soft_identity_hub
from remme.engines.evidence_log import get_evidence_log


# Known schema fields for normalization
KNOWN_FIELDS = {
    # Preferences Hub
    "verbosity": {"hub": "preferences", "path": "output_contract.verbosity", "type": "enum", "values": ["concise", "detailed", "balanced"]},
    "format": {"hub": "preferences", "path": "output_contract.format", "type": "enum", "values": ["markdown", "plain", "code_heavy"]},
    "clarifications": {"hub": "preferences", "path": "output_contract.clarifications", "type": "enum", "values": ["ask_always", "minimize", "never"]},
    
    # Operating Context Hub
    "primary_languages": {"hub": "context", "path": "developer_posture.primary_languages", "type": "list"},
    "package_manager_python": {"hub": "context", "path": "developer_posture.package_managers.python", "type": "string"},
    "package_manager_js": {"hub": "context", "path": "developer_posture.package_managers.javascript", "type": "string"},
    "location": {"hub": "context", "path": "environment.location_region", "type": "string"},
    
    # Soft Identity Hub - Food
    "dietary_style": {"hub": "soft_identity", "path": "food_and_dining.dietary_style", "type": "enum", "values": ["vegetarian", "vegan", "non-vegetarian", "pescatarian"]},
    "cuisine_likes": {"hub": "soft_identity", "path": "food_and_dining.cuisine_affinities.likes", "type": "list"},
    "cuisine_dislikes": {"hub": "soft_identity", "path": "food_and_dining.cuisine_affinities.dislikes", "type": "list"},
    "favorite_foods": {"hub": "soft_identity", "path": "food_and_dining.cuisine_affinities.favorites", "type": "list"},
    "food_allergies": {"hub": "soft_identity", "path": "food_and_dining.restrictions.allergies", "type": "list"},
    
    # Soft Identity Hub - Pets
    "pet_affinity": {"hub": "soft_identity", "path": "pets_and_animals.affinity", "type": "enum", "values": ["dog", "cat", "both", "other", "none"]},
    "pet_names": {"hub": "soft_identity", "path": "pets_and_animals.ownership.pet_names", "type": "list"},
    
    # Soft Identity Hub - Media
    "music_genres": {"hub": "soft_identity", "path": "media_and_entertainment.music.genres", "type": "list"},
    "movie_genres": {"hub": "soft_identity", "path": "media_and_entertainment.movies_tv.genres", "type": "list"},
    "book_genres": {"hub": "soft_identity", "path": "media_and_entertainment.books.genres", "type": "list"},
    
    # Soft Identity Hub - Interests
    "hobbies": {"hub": "soft_identity", "path": "interests_and_hobbies.personal_hobbies", "type": "list"},
    "professional_interests": {"hub": "soft_identity", "path": "interests_and_hobbies.professional_interests", "type": "list"},
    "learning_interests": {"hub": "soft_identity", "path": "interests_and_hobbies.learning_interests", "type": "list"},
    
    # Soft Identity Hub - Communication
    "humor_tolerance": {"hub": "soft_identity", "path": "communication_style.humor_tolerance", "type": "enum", "values": ["high", "medium", "low", "none"]},
    "small_talk_tolerance": {"hub": "soft_identity", "path": "communication_style.small_talk_tolerance", "type": "enum", "values": ["high", "medium", "low", "none"]},
    
    # Soft Identity Hub - Professional
    "industry": {"hub": "soft_identity", "path": "professional_context.industry", "type": "string"},
    "role_type": {"hub": "soft_identity", "path": "professional_context.role_type", "type": "string"},
    "experience_level": {"hub": "soft_identity", "path": "professional_context.experience_level", "type": "enum", "values": ["junior", "mid", "senior", "expert"]},
}


NORMALIZER_PROMPT = """You are a preference normalization AI.

Your job is to map raw extracted preferences to a standardized schema.

## KNOWN SCHEMA FIELDS
{known_fields}

## RAW EXTRACTED DATA
{raw_data}

## INSTRUCTIONS
1. For each raw key-value pair, determine if it matches a known field
2. If it matches, output the canonical field name
3. If it's a new concept not in the schema, mark it as "extras.<key_name>"
4. Detect if this is a NEW value or REINFORCES an existing value
5. Detect if this CONTRADICTS an existing value

## OUTPUT FORMAT
Return a JSON list:
```json
{{
  "mappings": [
    {{"raw_key": "diet", "field": "dietary_style", "value": "vegetarian", "is_new": false, "is_reinforcement": true, "is_contradiction": false}},
    {{"raw_key": "blood_type", "field": "extras.blood_group", "value": "B+", "is_new": true, "is_reinforcement": false, "is_contradiction": false}}
  ]
}}
```

Return ONLY valid JSON, no explanation."""


class Normalizer:
    """
    Normalizes raw extracted preferences to hub schema using LLM.
    """
    
    def __init__(self, model: str = None):
        self.model = model or get_model("memory_extraction")
        self.api_url = get_ollama_url("chat")
    
    def normalize(self, raw_data: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Normalize raw extracted preferences using LLM.
        
        Args:
            raw_data: Aggregated raw data from staging store
                      {key: [{value, source, timestamp}, ...]}
        
        Returns:
            List of normalized mappings
        """
        if not raw_data:
            return []
        
        # Format known fields for prompt
        fields_str = "\n".join([
            f"- {name}: {info['type']} ({info['path']})"
            for name, info in KNOWN_FIELDS.items()
        ])
        
        # Format raw data for prompt
        raw_str = json.dumps(raw_data, indent=2, default=str)
        
        prompt = NORMALIZER_PROMPT.format(
            known_fields=fields_str,
            raw_data=raw_str
        )
        
        try:
            response = requests.post(
                self.api_url,
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": "Normalize these preferences:"}
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
            
            parsed = json.loads(content)
            mappings = parsed.get("mappings", [])
            
            print(f"🔄 Normalized {len(mappings)} preferences")
            return mappings
            
        except Exception as e:
            print(f"❌ Normalization failed: {e}")
            return []
    
    def apply_to_hubs(self, mappings: List[Dict]) -> List[str]:
        """
        Apply normalized mappings to hubs with belief updates.
        
        Args:
            mappings: List of normalized mappings from normalize()
        
        Returns:
            List of changes made
        """
        prefs_hub = get_preferences_hub()
        context_hub = get_operating_context_hub()
        soft_hub = get_soft_identity_hub()
        evidence_log = get_evidence_log()
        belief_engine = get_belief_engine()
        
        changes = []
        
        for mapping in mappings:
            field = mapping.get("field")
            value = mapping.get("value")
            is_new = mapping.get("is_new", True)
            is_reinforcement = mapping.get("is_reinforcement", False)
            is_contradiction = mapping.get("is_contradiction", False)
            
            if not field or value is None:
                continue
            
            try:
                # Handle extras
                if field.startswith("extras."):
                    extra_key = field.replace("extras.", "")
                    if not hasattr(soft_hub.data, "extras"):
                        soft_hub.data.extras = {}
                    soft_hub.data.extras[extra_key] = {
                        "value": value,
                        "confidence": belief_engine.get_base_confidence("soft_identity"),
                        "evidence_count": 1,
                        "last_updated": datetime.now().isoformat()
                    }
                    changes.append(f"extras.{extra_key}={value}")
                    continue
                
                # Get field info
                field_info = KNOWN_FIELDS.get(field)
                if not field_info:
                    continue
                
                hub_name = field_info["hub"]
                
                # Calculate confidence update
                if is_reinforcement:
                    # Boost confidence
                    current_conf = 0.3  # TODO: Get actual current confidence
                    new_conf = belief_engine.calculate_confidence_update(
                        hub_name, current_conf, is_reinforcement=True
                    )
                    print(f"📈 Reinforced {field}: conf {current_conf:.2f} → {new_conf:.2f}")
                elif is_contradiction:
                    # Decrease confidence
                    current_conf = 0.5
                    new_conf = belief_engine.calculate_confidence_update(
                        hub_name, current_conf, is_reinforcement=False
                    )
                    print(f"📉 Contradiction on {field}: conf {current_conf:.2f} → {new_conf:.2f}")
                
                # Apply to appropriate hub
                self._apply_field_value(field, value, prefs_hub, context_hub, soft_hub)
                changes.append(f"{field}={value}")
                
            except Exception as e:
                print(f"⚠️ Failed to apply {field}: {e}")
        
        # Save all hubs
        if changes:
            prefs_hub.save()
            context_hub.save()
            soft_hub.save()
            
            evidence_log.add_event(
                source_type="normalizer",
                source_reference="batch_normalization",
                signal_category="normalized_preferences",
                raw_excerpt=f"Applied {len(changes)} normalized preferences",
                derived_updates=[{"operation": "batch_apply", "fields": changes}],
                confidence_impact=0.2
            )
            evidence_log.save()
            
            print(f"✅ Applied {len(changes)} normalized preferences to hubs")
        
        return changes
    
    def _apply_field_value(self, field: str, value: Any, prefs_hub, context_hub, soft_hub):
        """Apply a single field value to the appropriate hub."""
        
        # Map fields to setter methods
        setters = {
            "verbosity": lambda v: prefs_hub.set_verbosity(v),
            "format": lambda v: prefs_hub.set_format(v),
            "dietary_style": lambda v: soft_hub.set_dietary_style(v),
            "pet_affinity": lambda v: soft_hub.set_pet_affinity(v),
            "humor_tolerance": lambda v: soft_hub.set_humor_tolerance(v),
            "small_talk_tolerance": lambda v: soft_hub.set_small_talk_tolerance(v),
            "experience_level": lambda v: soft_hub.set_experience_level(v),
        }
        
        # List appenders
        list_appenders = {
            "primary_languages": lambda v: context_hub.add_primary_language(v, "normalizer"),
            "cuisine_likes": lambda v: soft_hub.add_cuisine_like(v),
            "cuisine_dislikes": lambda v: soft_hub.add_cuisine_dislike(v),
            "music_genres": lambda v: soft_hub.add_music_genre(v),
            "hobbies": lambda v: soft_hub.add_hobby(v),
            "professional_interests": lambda v: soft_hub.add_professional_interest(v),
        }
        
        if field in setters:
            setters[field](value)
        elif field in list_appenders:
            if isinstance(value, list):
                for item in value:
                    list_appenders[field](item)
            else:
                list_appenders[field](value)


async def run_normalizer():
    """
    Run the normalization pipeline.
    
    Reads from staging, normalizes via LLM, applies to hubs.
    """
    staging = get_staging_store()
    
    if staging.get_pending_count() == 0:
        print("📭 No pending preferences to normalize")
        return []
    
    print(f"🔄 Normalizing {staging.get_pending_count()} pending preferences...")
    
    # Get aggregated raw data
    raw_data = staging.get_all_raw_values()
    
    # Normalize via LLM
    normalizer = Normalizer()
    mappings = normalizer.normalize(raw_data)
    
    # Apply to hubs
    changes = normalizer.apply_to_hubs(mappings)
    
    # Clear staging
    staging.clear_pending()
    
    return changes
