"""
Central registry for canonical Fact fields (P11 Mnemo).

Single source of truth: defines canonical namespace+key, value_type, hub path,
append semantics, and aliases. Used by fact_normalizer (ingestion) and
neo4j_preferences_adapter (read path).

Add new list-valued fields here with aliases; no changes needed in knowledge_graph
or adapter.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Field definition: (namespace, key, value_type, hub_path, append)
# hub_path: tuple for response path, e.g. ("soft_identity", "interests_and_hobbies", "personal_hobbies")
# append: True if value should be merged into a list
FIELD_DEFS: Dict[str, Dict[str, Any]] = {
    # preferences
    "verbosity.default": {
        "namespace": "preferences.output_contract",
        "key": "verbosity.default",
        "value_type": "text",
        "hub_path": ("preferences", "output_contract", "verbosity"),
        "append": False,
    },
    "verbosity": {
        "namespace": "preferences.output_contract",
        "key": "verbosity",
        "value_type": "text",
        "hub_path": ("preferences", "output_contract", "verbosity"),
        "append": False,
    },
    "format.default": {
        "namespace": "preferences.output_contract",
        "key": "format.default",
        "value_type": "text",
        "hub_path": ("preferences", "output_contract", "format"),
        "append": False,
    },
    "format": {
        "namespace": "preferences.output_contract",
        "key": "format",
        "value_type": "text",
        "hub_path": ("preferences", "output_contract", "format"),
        "append": False,
    },
    "tone": {
        "namespace": "preferences.output_contract",
        "key": "tone",
        "value_type": "json",
        "hub_path": ("preferences", "output_contract", "tone_constraints"),
        "append": True,
    },
    "clarifications": {
        "namespace": "preferences.output_contract",
        "key": "clarifications",
        "value_type": "text",
        "hub_path": ("preferences", "output_contract", "clarifications"),
        "append": False,
    },
    "package_manager.python": {
        "namespace": "tooling.package_manager",
        "key": "python",
        "value_type": "text",
        "hub_path": ("preferences", "tooling", "package_manager", "python"),
        "append": False,
    },
    "package_manager.javascript": {
        "namespace": "tooling.package_manager",
        "key": "javascript",
        "value_type": "text",
        "hub_path": ("preferences", "tooling", "package_manager", "javascript"),
        "append": False,
    },
    "frameworks_frontend": {
        "namespace": "preferences",
        "key": "frameworks_frontend",
        "value_type": "json",
        "hub_path": ("preferences", "tooling", "frameworks", "frontend"),
        "append": True,
    },
    "frameworks_backend": {
        "namespace": "preferences",
        "key": "frameworks_backend",
        "value_type": "json",
        "hub_path": ("preferences", "tooling", "frameworks", "backend"),
        "append": True,
    },
    # operating_context
    "os": {
        "namespace": "operating.environment",
        "key": "os",
        "value_type": "text",
        "hub_path": ("operating_context", "os"),
        "append": False,
    },
    "location": {
        "namespace": "operating.environment",
        "key": "location",
        "value_type": "text",
        "hub_path": ("operating_context", "location"),
        "append": False,
    },
    "primary_languages": {
        "namespace": "operating.context",
        "key": "primary_languages",
        "value_type": "json",
        "hub_path": ("operating_context", "primary_languages"),
        "append": True,
    },
    # soft_identity
    "dietary_style": {
        "namespace": "identity.food",
        "key": "dietary_style",
        "value_type": "text",
        "hub_path": ("soft_identity", "food_and_dining", "dietary_style"),
        "append": False,
    },
    "cuisine_likes": {
        "namespace": "identity.food",
        "key": "cuisine_likes",
        "value_type": "json",
        "hub_path": ("soft_identity", "food_and_dining", "cuisine_likes"),
        "append": True,
    },
    "cuisine_dislikes": {
        "namespace": "identity.food",
        "key": "cuisine_dislikes",
        "value_type": "json",
        "hub_path": ("soft_identity", "food_and_dining", "cuisine_dislikes"),
        "append": True,
    },
    "favorite_foods": {
        "namespace": "identity.food",
        "key": "favorite_foods",
        "value_type": "json",
        "hub_path": ("soft_identity", "food_and_dining", "favorite_foods"),
        "append": True,
    },
    "pet_affinity": {
        "namespace": "identity",
        "key": "pet_affinity",
        "value_type": "text",
        "hub_path": ("soft_identity", "pets_and_animals", "affinity"),
        "append": False,
    },
    "pet_names": {
        "namespace": "identity",
        "key": "pet_names",
        "value_type": "json",
        "hub_path": ("soft_identity", "pets_and_animals", "pet_names"),
        "append": True,
    },
    "music_genres": {
        "namespace": "identity",
        "key": "music_genres",
        "value_type": "json",
        "hub_path": ("soft_identity", "media_and_entertainment", "music_genres"),
        "append": True,
    },
    "movie_genres": {
        "namespace": "identity",
        "key": "movie_genres",
        "value_type": "json",
        "hub_path": ("soft_identity", "media_and_entertainment", "movie_genres"),
        "append": True,
    },
    "humor_tolerance": {
        "namespace": "identity",
        "key": "humor_tolerance",
        "value_type": "text",
        "hub_path": ("soft_identity", "communication_style", "humor_tolerance"),
        "append": False,
    },
    "small_talk_tolerance": {
        "namespace": "identity",
        "key": "small_talk_tolerance",
        "value_type": "text",
        "hub_path": ("soft_identity", "communication_style", "small_talk_tolerance"),
        "append": False,
    },
    "personal_hobbies": {
        "namespace": "identity",
        "key": "personal_hobbies",
        "value_type": "json",
        "hub_path": ("soft_identity", "interests_and_hobbies", "personal_hobbies"),
        "append": True,
    },
    "professional_interests": {
        "namespace": "identity",
        "key": "professional_interests",
        "value_type": "json",
        "hub_path": ("soft_identity", "interests_and_hobbies", "professional_interests"),
        "append": True,
    },
    "learning_interests": {
        "namespace": "identity",
        "key": "learning_interests",
        "value_type": "json",
        "hub_path": ("soft_identity", "interests_and_hobbies", "learning_interests"),
        "append": True,
    },
    "side_projects": {
        "namespace": "identity",
        "key": "side_projects",
        "value_type": "json",
        "hub_path": ("soft_identity", "interests_and_hobbies", "side_projects"),
        "append": True,
    },
    "industry": {
        "namespace": "identity",
        "key": "industry",
        "value_type": "text",
        "hub_path": ("soft_identity", "professional_context", "industry"),
        "append": False,
    },
    "role_type": {
        "namespace": "identity",
        "key": "role_type",
        "value_type": "text",
        "hub_path": ("soft_identity", "professional_context", "role_type"),
        "append": False,
    },
    "experience_level": {
        "namespace": "identity",
        "key": "experience_level",
        "value_type": "text",
        "hub_path": ("soft_identity", "professional_context", "experience_level"),
        "append": False,
    },
}

# Alias: (namespace, key) -> field_id
# LLM may output variants; these map to canonical fields
ALIAS_TO_FIELD: Dict[Tuple[str, str], str] = {}
for field_id, defn in FIELD_DEFS.items():
    ns = defn["namespace"]
    key = defn["key"]
    ALIAS_TO_FIELD[(ns, key)] = field_id
# Aliases for variants the LLM might output
_ALIAS_OVERRIDES: List[Tuple[str, str, str]] = [
    ("preferences.output_contract", "verbosity", "verbosity.default"),
    ("preferences.output_contract", "format", "format.default"),
    ("operating_context", "location", "location"),
    ("operating", "primary_languages", "primary_languages"),
    ("identity", "hobbies", "personal_hobbies"),
    ("identity", "hobby", "personal_hobbies"),
    ("identity.hobby", "hobby", "personal_hobbies"),
]
for alias_ns, alias_key, field_id in _ALIAS_OVERRIDES:
    ALIAS_TO_FIELD[(alias_ns, alias_key)] = field_id


def resolve_to_canonical(ns: str, key: str) -> Optional[Tuple[str, str, str, Tuple[str, ...], bool]]:
    """
    Resolve (namespace, key) to canonical field.
    Returns (target_ns, target_key, value_type, hub_path, append) or None.
    """
    field_id = ALIAS_TO_FIELD.get((ns, key))
    if not field_id:
        return None
    defn = FIELD_DEFS.get(field_id)
    if not defn:
        return None
    return (
        defn["namespace"],
        defn["key"],
        defn["value_type"],
        defn["hub_path"],
        defn["append"],
    )


def get_hub_path(ns: str, key: str) -> Optional[Tuple[Tuple[str, ...], bool]]:
    """Get (hub_path, append) for a Fact (namespace, key), or None if not registered."""
    r = resolve_to_canonical(ns, key)
    if not r:
        return None
    _, _, _, hub_path, append = r
    return (hub_path, append)


def get_fact_to_hub_mappings() -> List[Tuple[str, str, Tuple[str, ...], bool]]:
    """Build (namespace, key, hub_path, append) for adapter. Includes all canonical + aliases."""
    seen: set = set()
    out: List[Tuple[str, str, Tuple[str, ...], bool]] = []
    for (alias_ns, alias_key), field_id in ALIAS_TO_FIELD.items():
        key = (alias_ns, alias_key)
        if key in seen:
            continue
        seen.add(key)
        defn = FIELD_DEFS.get(field_id)
        if defn:
            out.append((alias_ns, alias_key, defn["hub_path"], defn["append"]))
    return out


def get_list_append_targets() -> Dict[Tuple[str, str], Tuple[str, str]]:
    """Get (source_ns, source_key) -> (target_ns, target_key) for list-append facts."""
    result: Dict[Tuple[str, str], Tuple[str, str]] = {}
    for (alias_ns, alias_key), field_id in ALIAS_TO_FIELD.items():
        defn = FIELD_DEFS.get(field_id)
        if defn and defn["append"]:
            target_ns = defn["namespace"]
            target_key = defn["key"]
            result[(alias_ns, alias_key)] = (target_ns, target_key)
    return result
