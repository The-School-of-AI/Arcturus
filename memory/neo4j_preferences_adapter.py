"""
Neo4j Preferences Adapter — Build hub-shaped response from Neo4j Facts (P11 Mnemo Step 4).

Reads Facts for a user and produces the same structure as GET /remme/preferences
(output_contract, operating_context, soft_identity, evidence, meta).
Map Fact namespace+key to response paths; resolve conflicts by confidence and last_seen_at.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# Mapping: (namespace, key) -> (path_in_response, append_to_list).
# path is tuple like ("preferences", "output_contract", "verbosity").
# append_to_list: if True, value is appended to a list at that path.
FACT_TO_HUB_PATH: List[Tuple[str, str, Tuple[str, ...], bool]] = [
    # preferences.output_contract
    ("preferences.output_contract", "verbosity.default", ("preferences", "output_contract", "verbosity"), False),
    ("preferences.output_contract", "verbosity", ("preferences", "output_contract", "verbosity"), False),
    ("preferences.output_contract", "format.default", ("preferences", "output_contract", "format"), False),
    ("preferences.output_contract", "format", ("preferences", "output_contract", "format"), False),
    ("preferences.output_contract", "tone", ("preferences", "output_contract", "tone_constraints"), True),
    ("preferences.output_contract", "clarifications", ("preferences", "output_contract", "clarifications"), False),
    # tooling
    ("tooling.package_manager", "python", ("preferences", "tooling", "package_manager", "python"), False),
    ("tooling.package_manager", "javascript", ("preferences", "tooling", "package_manager", "javascript"), False),
    ("preferences", "frameworks_frontend", ("preferences", "tooling", "frameworks", "frontend"), True),
    ("preferences", "frameworks_backend", ("preferences", "tooling", "frameworks", "backend"), True),
    # operating_context
    ("operating.environment", "os", ("operating_context", "os"), False),
    ("operating.environment", "location", ("operating_context", "location"), False),
    ("operating_context", "location", ("operating_context", "location"), False),
    ("operating.context", "primary_languages", ("operating_context", "primary_languages"), True),
    ("operating", "primary_languages", ("operating_context", "primary_languages"), True),
    # soft_identity
    ("identity.food", "dietary_style", ("soft_identity", "food_and_dining", "dietary_style"), False),
    ("identity.food", "cuisine_likes", ("soft_identity", "food_and_dining", "cuisine_likes"), True),
    ("identity.food", "cuisine_dislikes", ("soft_identity", "food_and_dining", "cuisine_dislikes"), True),
    ("identity.food", "favorite_foods", ("soft_identity", "food_and_dining", "favorite_foods"), True),
    ("identity", "pet_affinity", ("soft_identity", "pets_and_animals", "affinity"), False),
    ("identity", "pet_names", ("soft_identity", "pets_and_animals", "pet_names"), True),
    ("identity", "music_genres", ("soft_identity", "media_and_entertainment", "music_genres"), True),
    ("identity", "movie_genres", ("soft_identity", "media_and_entertainment", "movie_genres"), True),
    ("identity", "humor_tolerance", ("soft_identity", "communication_style", "humor_tolerance"), False),
    ("identity", "small_talk_tolerance", ("soft_identity", "communication_style", "small_talk_tolerance"), False),
    ("identity", "hobbies", ("soft_identity", "interests_and_hobbies", "personal_hobbies"), True),
    ("identity", "personal_hobbies", ("soft_identity", "interests_and_hobbies", "personal_hobbies"), True),
    ("identity", "professional_interests", ("soft_identity", "interests_and_hobbies", "professional_interests"), True),
    ("identity", "learning_interests", ("soft_identity", "interests_and_hobbies", "learning_interests"), True),
    ("identity", "side_projects", ("soft_identity", "interests_and_hobbies", "side_projects"), True),
    ("identity", "industry", ("soft_identity", "professional_context", "industry"), False),
    ("identity", "role_type", ("soft_identity", "professional_context", "role_type"), False),
    ("identity", "experience_level", ("soft_identity", "professional_context", "experience_level"), False),
]


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


def build_preferences_from_neo4j(user_id: str) -> Dict[str, Any]:
    """
    Build the GET /remme/preferences response shape from Neo4j Facts.

    Returns the same structure as the legacy hub-based response so the UI
    and other consumers need no changes.
    """
    from memory.knowledge_graph import get_knowledge_graph
    from memory.mnemo_config import is_mnemo_enabled

    if not is_mnemo_enabled():
        return {}
    kg = get_knowledge_graph()
    if not kg or not kg.enabled:
        return {}

    facts = kg.get_facts_for_user(user_id)
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
        prev = used.get(path_tup, (0, None))
        if confidence > prev[0] or (confidence == prev[0] and last_seen and (prev[1] or "") < str(last_seen)):
            used[path_tup] = (confidence, str(last_seen) if last_seen else None)
            _set_nested(result, path_tup, val, append)

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
