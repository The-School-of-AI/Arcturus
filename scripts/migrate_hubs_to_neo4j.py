#!/usr/bin/env python3
"""
Migrate JSON hub data (preferences, operating_context, soft_identity) to Neo4j Fact nodes.

One-time script for P11 Mnemo Step 5. Reads hub JSON files, maps fields to Fact
(namespace, key, value), creates Fact nodes with source_mode=migration, and
optional Evidence from evidence_log. Runs derivation for User–Entity edges.

Prerequisites:
    - NEO4J_ENABLED=true, NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD
    - MNEMO_ENABLED=true (optional; script creates Facts regardless)

Usage:
    uv run python scripts/migrate_hubs_to_neo4j.py
    uv run python scripts/migrate_hubs_to_neo4j.py --dry-run
"""

import argparse
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

from memory.knowledge_graph import get_knowledge_graph
from memory.user_id import get_user_id
from core.utils import log_step, log_error


HUB_PATHS = {
    "preferences": ROOT / "memory" / "user_model" / "preferences_hub.json",
    "operating_context": ROOT / "memory" / "user_model" / "operating_context_hub.json",
    "soft_identity": ROOT / "memory" / "user_model" / "soft_identity_hub.json",
    "evidence_log": ROOT / "memory" / "user_model" / "evidence_log.json",
}


def _val(obj: Any) -> Any:
    """Extract value from ConfidenceField, ScopedValue, or raw."""
    if obj is None:
        return None
    if hasattr(obj, "value") and obj.value is not None:
        return obj.value
    if hasattr(obj, "default") and obj.default is not None:
        return obj.default
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, dict)) and obj:
        return obj
    return None


def _conf(obj: Any) -> float:
    """Extract confidence from ConfidenceField or similar."""
    if obj is None:
        return 0.5
    return float(getattr(obj, "confidence", 0.5) or 0.5)


def _valid_list_item(x: Any) -> bool:
    """Exclude None, empty, and literal 'null' string from list values."""
    if x is None:
        return False
    if isinstance(x, str) and (not x.strip() or x.strip().lower() == "null"):
        return False
    return True


def _valid_scalar(val: Any) -> bool:
    """Exclude None, empty, and literal 'null' string from scalar values."""
    if val is None:
        return False
    if isinstance(val, str) and (not val.strip() or val.strip().lower() == "null"):
        return False
    return True


def extract_facts_from_preferences(data: Dict[str, Any]) -> List[Tuple[str, str, Any, str, float]]:
    """Extract (namespace, key, value, value_type, confidence) from preferences hub."""
    facts: List[Tuple[str, str, Any, str, float]] = []
    meta_conf = float(data.get("meta", {}).get("confidence", 0.5) or 0.5)

    oc = data.get("output_contract", {})
    if oc:
        v = oc.get("verbosity", {})
        vdef = v.get("default") if isinstance(v, dict) else getattr(v, "default", None)
        if _valid_scalar(vdef):
            facts.append(("preferences.output_contract", "verbosity.default", vdef, "text", _conf(v)))

        f = oc.get("format_defaults", oc.get("format", {}))
        fdef = f.get("default") if isinstance(f, dict) else getattr(f, "default", None)
        if _valid_scalar(fdef):
            facts.append(("preferences.output_contract", "format.default", fdef, "text", _conf(f)))

        tone = oc.get("tone_constraints", [])
        if isinstance(tone, list):
            tone = [t for t in tone if _valid_list_item(t)]
            if tone:
                facts.append(("preferences.output_contract", "tone", tone, "json", meta_conf))

        qp = oc.get("questions_policy", {})
        c = qp.get("clarifications") if isinstance(qp, dict) else getattr(qp, "clarifications", None)
        if _valid_scalar(c):
            facts.append(("preferences.output_contract", "clarifications", c, "text", meta_conf))

    tooling = data.get("tooling_defaults", {})
    if tooling:
        pm = tooling.get("package_manager", tooling.get("package_managers", {}))
        if isinstance(pm, dict):
            py_ = pm.get("python")
            if _valid_scalar(py_):
                facts.append(("tooling.package_manager", "python", py_, "text", meta_conf))
            js_ = pm.get("javascript")
            if _valid_scalar(js_):
                facts.append(("tooling.package_manager", "javascript", js_, "text", meta_conf))
        fw = tooling.get("frameworks", {})
        if isinstance(fw, dict):
            fe = [x for x in (fw.get("frontend", []) or []) if _valid_list_item(x)]
            if fe:
                facts.append(("preferences", "frameworks_frontend", fe, "json", meta_conf))
            be = [x for x in (fw.get("backend", []) or []) if _valid_list_item(x)]
            if be:
                facts.append(("preferences", "frameworks_backend", be, "json", meta_conf))

    return facts


def extract_facts_from_operating_context(data: Dict[str, Any]) -> List[Tuple[str, str, Any, str, float]]:
    """Extract (namespace, key, value, value_type, confidence) from operating_context hub."""
    facts: List[Tuple[str, str, Any, str, float]] = []
    meta_conf = float(data.get("meta", {}).get("confidence", 0.5) or 0.5)

    env = data.get("environment", {})
    if env:
        os_ = env.get("os", {})
        os_val = os_.get("value") if isinstance(os_, dict) else getattr(os_, "value", None)
        if _valid_scalar(os_val):
            facts.append(("operating.environment", "os", os_val, "text", _conf(os_)))
        loc = env.get("location_region", {})
        loc_val = loc.get("value") if isinstance(loc, dict) else getattr(loc, "value", None)
        if _valid_scalar(loc_val):
            facts.append(("operating.environment", "location", loc_val, "text", _conf(loc)))

    dev = data.get("developer_posture", {})
    if dev:
        pl = dev.get("primary_languages", {})
        ranked = pl.get("ranked", []) if isinstance(pl, dict) else getattr(pl, "ranked", [])
        langs = [x for x in (ranked or []) if _valid_list_item(x)]
        if langs:
            facts.append(("operating.context", "primary_languages", langs, "json", meta_conf))

    return facts


def extract_facts_from_soft_identity(data: Dict[str, Any]) -> List[Tuple[str, str, Any, str, float]]:
    """Extract (namespace, key, value, value_type, confidence) from soft_identity hub."""
    facts: List[Tuple[str, str, Any, str, float]] = []
    meta_conf = float(data.get("meta", {}).get("confidence", 0.5) or 0.5)

    fd = data.get("food_and_dining", {})
    if fd:
        ds = fd.get("dietary_style", {})
        ds_val = ds.get("value") if isinstance(ds, dict) else getattr(ds, "value", None)
        if _valid_scalar(ds_val):
            facts.append(("identity.food", "dietary_style", ds_val, "text", _conf(ds)))
        ca = fd.get("cuisine_affinities", {})
        if isinstance(ca, dict):
            likes = [x for x in (ca.get("likes", []) or []) if _valid_list_item(x)]
            if likes:
                facts.append(("identity.food", "cuisine_likes", likes, "json", meta_conf))
            dislikes = [x for x in (ca.get("dislikes", []) or []) if _valid_list_item(x)]
            if dislikes:
                facts.append(("identity.food", "cuisine_dislikes", dislikes, "json", meta_conf))
            favs = [x for x in (ca.get("favorites", []) or []) if _valid_list_item(x)]
            if favs:
                facts.append(("identity.food", "favorite_foods", favs, "json", meta_conf))

    pa = data.get("pets_and_animals", {})
    if pa:
        aff = pa.get("affinity", {})
        aff_val = aff.get("value") if isinstance(aff, dict) else getattr(aff, "value", None)
        if _valid_scalar(aff_val):
            facts.append(("identity", "pet_affinity", aff_val, "text", _conf(aff)))
        own = pa.get("ownership", {})
        pnames = (own.get("pet_names", []) or []) if isinstance(own, dict) else (getattr(own, "pet_names", []) or [])
        pnames = [x for x in pnames if _valid_list_item(x)]
        if pnames:
            facts.append(("identity", "pet_names", pnames, "json", meta_conf))

    me = data.get("media_and_entertainment", {})
    if me:
        music_genres = (me.get("music", {}).get("genres", []) or []) if isinstance(me.get("music"), dict) else (getattr(me.get("music"), "genres", []) or [])
        music_genres = [x for x in music_genres if _valid_list_item(x)]
        if music_genres:
            facts.append(("identity", "music_genres", music_genres, "json", meta_conf))
        mt = me.get("movies_tv", {})
        movie_genres = (mt.get("genres", []) or []) if isinstance(mt, dict) else (getattr(mt, "genres", []) or [])
        movie_genres = [x for x in movie_genres if _valid_list_item(x)]
        if movie_genres:
            facts.append(("identity", "movie_genres", movie_genres, "json", meta_conf))

    cs = data.get("communication_style", {})
    if cs:
        ht = cs.get("humor_tolerance", {})
        ht_val = ht.get("value") if isinstance(ht, dict) else getattr(ht, "value", None)
        if _valid_scalar(ht_val):
            facts.append(("identity", "humor_tolerance", ht_val, "text", _conf(ht)))
        st = cs.get("small_talk_tolerance", {})
        st_val = st.get("value") if isinstance(st, dict) else getattr(st, "value", None)
        if _valid_scalar(st_val):
            facts.append(("identity", "small_talk_tolerance", st_val, "text", _conf(st)))

    ih = data.get("interests_and_hobbies", {})
    if ih:
        prof = [x for x in (ih.get("professional_interests", []) or []) if _valid_list_item(x)]
        if prof:
            facts.append(("identity", "professional_interests", prof, "json", meta_conf))
        hobbies = [x for x in (ih.get("personal_hobbies", []) or []) if _valid_list_item(x)]
        if hobbies:
            facts.append(("identity", "personal_hobbies", hobbies, "json", meta_conf))
        learn = [x for x in (ih.get("learning_interests", []) or []) if _valid_list_item(x)]
        if learn:
            facts.append(("identity", "learning_interests", learn, "json", meta_conf))
        side = [x for x in (ih.get("side_projects", []) or []) if _valid_list_item(x)]
        if side:
            facts.append(("identity", "side_projects", side, "json", meta_conf))

    pc = data.get("professional_context", {})
    if pc:
        ind = pc.get("industry", {})
        ind_val = ind.get("value") if isinstance(ind, dict) else getattr(ind, "value", None)
        if _valid_scalar(ind_val):
            facts.append(("identity", "industry", ind_val, "text", _conf(ind)))
        rt = pc.get("role_type", {})
        rt_val = rt.get("value") if isinstance(rt, dict) else getattr(rt, "value", None)
        if _valid_scalar(rt_val):
            facts.append(("identity", "role_type", rt_val, "text", _conf(rt)))
        el = pc.get("experience_level", {})
        el_val = el.get("value") if isinstance(el, dict) else getattr(el, "value", None)
        if _valid_scalar(el_val):
            facts.append(("identity", "experience_level", el_val, "text", _conf(el)))

    extras = data.get("extras", {})
    if isinstance(extras, dict):
        for k, v in extras.items():
            if v is not None and (not isinstance(v, (list, dict)) or v):
                facts.append(("extras", k, json.dumps(v) if isinstance(v, (list, dict)) else str(v), "json" if isinstance(v, (list, dict)) else "text", meta_conf))

    return facts


def main() -> int:
    parser = argparse.ArgumentParser(description="Migrate JSON hubs to Neo4j Fact nodes")
    parser.add_argument("--dry-run", action="store_true", help="Print facts only, skip Neo4j writes")
    parser.add_argument("--user-id", type=str, default=None, help="User ID (default: from get_user_id())")
    args = parser.parse_args()

    user_id = args.user_id or get_user_id()
    kg = get_knowledge_graph()
    if not kg or not kg.enabled:
        log_error("Neo4j not enabled. Set NEO4J_ENABLED=true and connection vars.")
        return 1

    all_facts: List[Tuple[str, str, Any, str, float]] = []
    for hub_name, path in HUB_PATHS.items():
        if hub_name == "evidence_log":
            continue
        if not path.exists():
            print(f"  Skipping {hub_name}: {path} not found")
            continue
        try:
            raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            if hub_name == "preferences":
                all_facts.extend(extract_facts_from_preferences(raw))
            elif hub_name == "operating_context":
                all_facts.extend(extract_facts_from_operating_context(raw))
            elif hub_name == "soft_identity":
                all_facts.extend(extract_facts_from_soft_identity(raw))
            print(f"  Loaded {hub_name}: {path}")
        except Exception as e:
            log_error(f"Failed to load {hub_name}: {e}")
            continue

    if not all_facts:
        print("No facts to migrate.")
        return 0

    print(f"\nMigrating {len(all_facts)} facts to Neo4j for user {user_id[:8]}...")
    kg.get_or_create_user(user_id)

    created = 0
    for ns, key, val, vt, conf in all_facts:
        if val is None or val == "" or val == "null" or (isinstance(val, (list, dict)) and not val):
            continue
        if args.dry_run:
            print(f"  [DRY-RUN] {ns}.{key} = {str(val)[:60]}... (conf={conf})")
            created += 1
            continue
        vt_text = str(val) if vt == "text" else None
        vt_num = float(val) if vt == "number" and isinstance(val, (int, float)) else None
        vt_bool = bool(val) if vt == "bool" else None
        vt_json = val if vt == "json" and isinstance(val, (list, dict)) else None
        fid = kg.upsert_fact(
            user_id=user_id,
            namespace=ns,
            key=key,
            value_type=vt,
            value_text=vt_text,
            value_number=vt_num,
            value_bool=vt_bool,
            value_json=vt_json,
            confidence=conf,
            source_mode="migration",
            entity_ref=None,
        )
        if fid:
            created += 1
            kg.create_evidence(
                evidence_id=str(uuid.uuid4()),
                source_type="migration",
                source_ref="hub_migration",
                user_id=user_id,
                namespace=ns,
                key=key,
                session_id=None,
                memory_id=None,
                timestamp=None,
            )

    if not args.dry_run and all_facts:
        facts_for_derive = [{"namespace": ns, "key": key, "entity_ref": None} for ns, key, _, _, _ in all_facts]
        kg._derive_user_entity_from_facts(user_id, facts_for_derive, {}, source_memory_ids=[])
        backfilled = kg.backfill_value_preview_for_user(user_id)
        if backfilled:
            print(f"  Backfilled value_preview on {backfilled} existing Fact(s)")

    log_step(f"Migrated {created} facts to Neo4j", symbol="✅")
    return 0


if __name__ == "__main__":
    sys.exit(main())
