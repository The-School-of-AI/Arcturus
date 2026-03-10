"""
Neo4j Preferences Adapter — Build hub-shaped response from Neo4j Facts (P11 Mnemo Step 4).

Reads Facts for a user and produces the same structure as GET /remme/preferences
(output_contract, operating_context, soft_identity, evidence, meta).
Map Fact namespace+key to response paths; resolve conflicts by confidence and last_seen_at.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from memory.fact_field_registry import get_fact_to_hub_mappings

# Mapping: (namespace, key) -> (path_in_response, append_to_list). Built from registry.
FACT_TO_HUB_PATH: List[Tuple[str, str, Tuple[str, ...], bool]] = get_fact_to_hub_mappings()


def _set_nested(d: Dict[str, Any], path: Tuple[str, ...], value: Any, append: bool) -> None:
    """Set d[path[0]][path[1]]... = value, or append/extend list if append=True."""
    current = d
    for i, key in enumerate(path[:-1]):
        if key not in current:
            current[key] = {}
        current = current[key]
    last = path[-1]
    if append:
        if last not in current:
            current[last] = []
        if isinstance(current[last], list):
            if isinstance(value, list):
                for v in value:
                    if v not in current[last]:
                        current[last].append(v)
            elif value not in current[last]:
                current[last].append(value)
    else:
        current[last] = value


def _default_hub_shape() -> Dict[str, Any]:
    """Return the default empty structure matching GET /remme/preferences response."""
    return {
        "preferences": {
            "output_contract": {
                "verbosity": "balanced",
                "format": "markdown",
                "tone_constraints": [],
                "structure_rules": [],
                "clarifications": "minimize",
            },
            "anti_preferences": {"phrases": [], "moves": []},
            "tooling": {
                "frameworks": {"frontend": [], "backend": []},
                "package_manager": {"python": "pip", "javascript": "npm"},
            },
            "autonomy": {
                "create_files": "allowed",
                "run_shell": "allowed",
                "delete_files": "allowed",
                "git_operations": "allowed",
            },
            "risk_tolerance": "moderate",
        },
        "operating_context": {
            "os": "unknown",
            "shell": "unknown",
            "cpu_architecture": "unknown",
            "primary_languages": [],
            "has_gpu": False,
            "assumption_limits": {},
            "location": None,
        },
        "soft_identity": {
            "extras": {},
            "food_and_dining": {
                "dietary_style": None,
                "cuisine_likes": [],
                "cuisine_dislikes": [],
                "favorite_foods": [],
                "food_allergies": [],
            },
            "pets_and_animals": {"affinity": None, "pet_names": []},
            "lifestyle_and_wellness": {
                "activity_level": None,
                "sleep_rhythm": None,
                "travel_style": None,
            },
            "media_and_entertainment": {
                "music_genres": [],
                "movie_genres": [],
                "book_genres": [],
                "podcast_genres": [],
            },
            "communication_style": {
                "humor_tolerance": None,
                "small_talk_tolerance": None,
                "formality_preference": None,
            },
            "interests_and_hobbies": {
                "professional_interests": [],
                "personal_hobbies": [],
                "learning_interests": [],
                "side_projects": [],
            },
            "professional_context": {
                "industry": None,
                "role_type": None,
                "experience_level": None,
                "team_size": None,
            },
        },
    }


def build_preferences_from_neo4j(
    user_id: str,
    space_id: Optional[str] = None,
    space_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Build the GET /remme/preferences response shape from Neo4j Facts.
    Phase 3B: optional space_id/space_ids filter. When provided, returns
    global facts + facts in requested space(s).
    """
    from memory.knowledge_graph import get_knowledge_graph
    from memory.mnemo_config import is_mnemo_enabled

    if not is_mnemo_enabled():
        return {}
    kg = get_knowledge_graph()
    if not kg or not kg.enabled:
        return {}

    facts = kg.get_facts_for_user(user_id, space_id=space_id, space_ids=space_ids)
    evidence = kg.get_evidence_count_for_user(user_id)

    result = _default_hub_shape()
    used: Dict[Tuple[str, ...], Tuple[float, Optional[str]]] = {}  # path -> (confidence, last_seen_at)

    for f in facts:
        ns = f.get("namespace") or ""
        key = f.get("key") or ""
        val = f.get("value")
        confidence = f.get("confidence") or 0
        last_seen = f.get("last_seen_at")
        if val is None and f.get("value_text") is not None:
            val = f.get("value_text")
        if val is None:
            continue
        if isinstance(val, bool) and not val and f.get("value_type") != "bool":
            continue
        path_tup: Optional[Tuple[str, ...]] = None
        append = False
        for m_ns, m_key, m_path, m_append in FACT_TO_HUB_PATH:
            if ns == m_ns and key == m_key:
                path_tup = m_path
                append = m_append
                break
            if ns.startswith(m_ns) and m_key == "*":
                path_tup = m_path
                append = m_append
                break
        if path_tup is None:
            result["soft_identity"]["extras"][f"{ns}.{key}"] = val
            continue
        # For append=True (list merge), always add from every matching fact
        # For append=False, use confidence/last_seen to resolve conflicts
        if append:
            _set_nested(result, path_tup, val, append=True)
        else:
            prev = used.get(path_tup, (0, None))
            if confidence > prev[0] or (confidence == prev[0] and last_seen and (prev[1] or "") < str(last_seen)):
                used[path_tup] = (confidence, str(last_seen) if last_seen else None)
                _set_nested(result, path_tup, val, append=False)

    avg_conf = (sum(u[0] for u in used.values()) / len(used)) if used else 0
    total_ev = evidence.get("total_events", 0)

    return {
        "status": "success",
        "preferences": result["preferences"],
        "operating_context": result["operating_context"],
        "soft_identity": result["soft_identity"],
        "evidence": {
            "total_events": total_ev,
            "events_by_source": evidence.get("events_by_source", {}),
            "events_by_type": evidence.get("events_by_type", {}),
        },
        "meta": {
            "preferences_confidence": avg_conf,
            "preferences_evidence_count": total_ev,
            "context_confidence": avg_conf,
            "soft_identity_confidence": avg_conf,
            "total_evidence": total_ev,
            "overall_confidence": avg_conf,
        },
    }
