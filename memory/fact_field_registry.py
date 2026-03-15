"""
Central registry for canonical Fact fields (P11 Mnemo).

field_id is the ONLY canonical fact identifier. The LLM must NOT invent
namespace or key; it selects a valid field_id from this registry.
Registry owns: field_id → namespace, key, value_type, append, hub_path, aliases.

Used by: fact_normalizer (ingestion), neo4j_preferences_adapter (read path),
extractor skill (valid field_ids for prompt).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Field definition: (namespace, key, value_type, hub_path, append, scope)
# hub_path: tuple for response path, e.g. ("soft_identity", "interests_and_hobbies", "personal_hobbies")
# append: True if value should be merged into a list
# scope: "global" | "space" — global facts valid everywhere; space-scoped facts per Space (Phase 3B)
FIELD_DEFS: Dict[str, Dict[str, Any]] = {
    # preferences
    "verbosity.default": {
        "namespace": "preferences.output_contract",
        "key": "verbosity.default",
        "value_type": "text",
        "hub_path": ("preferences", "output_contract", "verbosity"),
        "append": False,
        "scope": "global",
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

# Phase 3B: ensure all fields have scope (default "global")
for _fid, _defn in FIELD_DEFS.items():
    if "scope" not in _defn:
        _defn["scope"] = "global"

# Alias: (namespace, key) -> field_id (for adapter read path: Neo4j stores ns+key)
ALIAS_TO_FIELD: Dict[Tuple[str, str], str] = {}
for fid, defn in FIELD_DEFS.items():
    ns = defn["namespace"]
    k = defn["key"]
    ALIAS_TO_FIELD[(ns, k)] = fid
_ALIAS_OVERRIDES: List[Tuple[str, str, str]] = [
    ("preferences.output_contract", "verbosity", "verbosity.default"),
    ("preferences.output_contract", "format", "format.default"),
    ("operating_context", "location", "location"),
    ("operating", "primary_languages", "primary_languages"),
]
for alias_ns, alias_key, fid in _ALIAS_OVERRIDES:
    ALIAS_TO_FIELD[(alias_ns, alias_key)] = fid


def get_field_def(field_id: str) -> Optional[Dict[str, Any]]:
    """
    Lookup field by field_id. Returns full def or None.
    This is the primary resolution path for extractor output.
    """
    if not field_id or not isinstance(field_id, str):
        return None
    fid = (field_id or "").strip()
    return FIELD_DEFS.get(fid) if fid else None


def get_field_scope(field_id: str) -> str:
    """
    Return scope for field: "global" or "space". Phase 3B.
    Global facts valid everywhere; space-scoped facts per Space.
    Defaults to "global" when not set.
    """
    defn = get_field_def(field_id)
    if not defn:
        return "global"
    return (defn.get("scope") or "global").lower()


def get_valid_field_ids() -> List[str]:
    """Return sorted list of valid field_ids for extractor prompt."""
    return sorted(FIELD_DEFS.keys())


def resolve_field_id_to_canonical(field_id: str) -> Optional[Tuple[str, str, str, Tuple[str, ...], bool]]:
    """
    Resolve field_id to canonical (namespace, key, value_type, hub_path, append).
    Returns None if field_id is unknown.
    """
    defn = get_field_def(field_id)
    if not defn:
        return None
    return (
        defn["namespace"],
        defn["key"],
        defn["value_type"],
        defn["hub_path"],
        defn["append"],
    )


def get_scope_for_namespace_key(ns: str, key: str) -> str:
    """Get scope for (namespace, key). Defaults to global. Phase 3B."""
    field_id = ALIAS_TO_FIELD.get((ns, key))
    if field_id:
        return get_field_scope(field_id)
    for fid, defn in FIELD_DEFS.items():
        if defn.get("namespace") == ns and defn.get("key") == key:
            return get_field_scope(fid)
    return "global"


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
