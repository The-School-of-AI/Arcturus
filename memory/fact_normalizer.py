"""
Normalizes raw extracted facts to canonical fields (P11 Mnemo).

Maps aliases (e.g. identity.hobby/hobby) to canonical (identity/personal_hobbies),
merges list-valued facts, and returns normalized facts ready for ingestion.
Used by ingest_memory before upsert.
"""

from __future__ import annotations

import ast
import json
from typing import Any, Dict, List, Optional, Tuple

from memory.fact_field_registry import resolve_to_canonical


def _get_value(fact: Any) -> Optional[Any]:
    """Extract value from fact (dict or Pydantic). Prefer value_text/value_json/etc."""
    if isinstance(fact, dict):
        vt = fact.get("value_type", "text")
        if fact.get("value_text") is not None:
            return fact["value_text"]
        if fact.get("value_json") is not None:
            return fact["value_json"]
        if fact.get("value_number") is not None:
            return fact["value_number"]
        if fact.get("value_bool") is not None:
            return fact["value_bool"]
        val = fact.get("value")
        if val is not None:
            if vt == "json" and isinstance(val, list):
                return val
            if vt == "text":
                return str(val)
            return val
        return None
    # Pydantic
    vt = getattr(fact, "value_type", "text")
    if getattr(fact, "value_text", None) is not None:
        return fact.value_text
    if getattr(fact, "value_json", None) is not None:
        return fact.value_json
    if getattr(fact, "value_number", None) is not None:
        return fact.value_number
    if getattr(fact, "value_bool", None) is not None:
        return fact.value_bool
    val = getattr(fact, "value", None)
    if val is not None:
        if vt == "json" and isinstance(val, list):
            return val
        if vt == "text":
            return str(val)
        return val
    return None


def _to_values(val: Any) -> List[Any]:
    """Convert value to list of atomic values for merging into list facts."""
    if val is None:
        return []
    if isinstance(val, list):
        out: List[Any] = []
        for v in val:
            out.extend(_to_values(v))
        return out
    if isinstance(val, str) and val.strip().startswith(("[", "{")):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, list):
                return _to_values(parsed)
        except json.JSONDecodeError:
            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, list):
                    return _to_values(parsed)
            except (ValueError, SyntaxError):
                pass
    s = str(val).strip()
    if s and s.lower() != "null":
        return [s]
    return []


def normalize_facts(
    raw_facts: Optional[List[Any]] = None,
) -> List[Dict[str, Any]]:
    """
    Normalize raw extracted facts to canonical fields.
    - Maps aliases to canonical (ns, key)
    - Merges list-valued facts: multiple aliases mapping to same list field become one fact with merged values
    - Returns list of dicts: {namespace, key, value_type, value, value_text, value_json, append, entity_ref}
    """
    if not raw_facts:
        return []

    # Group by (target_ns, target_key); collect values for append fields
    scalar_facts: Dict[Tuple[str, str], Dict[str, Any]] = {}  # (ns, key) -> fact
    list_values: Dict[Tuple[str, str], List[Any]] = {}  # (ns, key) -> [values]

    for f in raw_facts:
        ns = f.get("namespace", "") if isinstance(f, dict) else getattr(f, "namespace", "")
        k = f.get("key", "") if isinstance(f, dict) else getattr(f, "key", "")
        if not ns or not k:
            continue

        r = resolve_to_canonical(ns, k)
        if not r:
            # Unknown field: pass through as-is (extras)
            out = {
                "namespace": ns,
                "key": k,
                "value_type": f.get("value_type", "text") if isinstance(f, dict) else getattr(f, "value_type", "text"),
                "value": _get_value(f),
                "append": False,
            }
            if isinstance(f, dict):
                out["entity_ref"] = f.get("entity_ref")
            else:
                out["entity_ref"] = getattr(f, "entity_ref", None)
            scalar_facts[(ns, k)] = out
            continue

        target_ns, target_key, value_type, _hub_path, append = r
        val = _get_value(f)
        entity_ref = f.get("entity_ref") if isinstance(f, dict) else getattr(f, "entity_ref", None)

        if append:
            key = (target_ns, target_key)
            vals = _to_values(val)
            if vals:
                if key not in list_values:
                    list_values[key] = []
                for v in vals:
                    if v not in list_values[key]:
                        list_values[key].append(v)
        else:
            if val is not None:
                scalar_facts[(target_ns, target_key)] = {
                    "namespace": target_ns,
                    "key": target_key,
                    "value_type": value_type,
                    "value": val,
                    "append": False,
                    "entity_ref": entity_ref,
                }

    out_list: List[Dict[str, Any]] = []
    for (ns, key), fact in scalar_facts.items():
        if (ns, key) in list_values:
            continue  # Prefer list merge over scalar for same canonical key
        out_list.append(fact)

    for (ns, key), vals in list_values.items():
        out_list.append({
            "namespace": ns,
            "key": key,
            "value_type": "json",
            "value_json": vals,
            "value": vals,
            "append": True,
            "entity_ref": None,  # List facts typically don't have entity_ref
        })

    return out_list
