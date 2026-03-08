"""
Normalizes extracted facts to canonical fields (P11 Mnemo).

LLM emits field_id only. Registry provides canonical (namespace, key).
Unknown field_id: log warning, route to extras. Never create canonical facts
from model-invented coordinates.
"""

from __future__ import annotations

import ast
import json
import logging
from typing import Any, Dict, List, Optional, Tuple

from memory.fact_field_registry import resolve_field_id_to_canonical

logger = logging.getLogger(__name__)


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
    Normalize facts using field_id only. Registry provides canonical (namespace, key).
    - Unknown field_id: log warning, route to extras (namespace="extras", key=field_id)
    - Merges list-valued facts by canonical (ns, key)
    - Returns: [{namespace, key, value_type, value, value_json, append, entity_ref}]
    """
    if not raw_facts:
        return []

    scalar_facts: Dict[Tuple[str, str], Dict[str, Any]] = {}
    list_values: Dict[Tuple[str, str], List[Any]] = {}

    for f in raw_facts:
        field_id = f.get("field_id", "") if isinstance(f, dict) else getattr(f, "field_id", "")
        field_id = (field_id or "").strip()
        if not field_id:
            continue

        r = resolve_field_id_to_canonical(field_id)
        if not r:
            logger.warning("Unknown field_id '%s' from extractor; routing to extras", field_id)
            scalar_facts[("extras", field_id)] = {
                "namespace": "extras",
                "key": field_id,
                "value_type": f.get("value_type", "text") if isinstance(f, dict) else getattr(f, "value_type", "text"),
                "value": _get_value(f),
                "append": False,
                "entity_ref": f.get("entity_ref") if isinstance(f, dict) else getattr(f, "entity_ref", None),
            }
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
    for (ns, k), fact in scalar_facts.items():
        if (ns, k) in list_values:
            continue
        out_list.append(fact)
    for (ns, k), vals in list_values.items():
        out_list.append({
            "namespace": ns,
            "key": k,
            "value_type": "json",
            "value_json": vals,
            "value": vals,
            "append": True,
            "entity_ref": None,
        })
    return out_list
