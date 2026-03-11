# RemMe Router - Handles memory management, smart scan, and user profile
import asyncio
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel
import requests
import pdb

from shared.state import (
    get_remme_store,
    get_remme_extractor,
    PROJECT_ROOT,
)
from remme.utils import get_embedding
from core.model_manager import ModelManager

router = APIRouter(prefix="/remme", tags=["RemMe"])

# Get shared instances
remme_store = get_remme_store()
remme_extractor = get_remme_extractor()


# === Pydantic Models ===

class AddMemoryRequest(BaseModel):
    text: str
    category: str = "general"
    space_id: str | None = None


class CreateSpaceRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    sync_policy: str | None = None  # Phase 4: "sync" | "local_only"


class UpdateFactRequest(BaseModel):
    """Request body for UI-driven fact edit (step 7). All fields except namespace, key, value_type are optional."""
    namespace: str
    key: str
    value_type: str = "text"  # text | number | bool | json
    value: str | float | bool | list | dict | None = None
    value_text: str | None = None
    value_number: float | None = None
    value_bool: bool | None = None
    value_json: list | dict | None = None
    entity_ref: str | None = None
    space_id: str | None = None


# === Background Tasks ===

async def background_smart_scan():
    """Scan all past sessions that haven't been processed yet."""
    print("🧠 RemMe: Starting Smart Sync...")
    try:
        # 1. Identify what we have
        scanned_ids = remme_store.get_scanned_run_ids()
        print(f"🧠 RemMe: Found {len(scanned_ids)} already scanned sessions.")
        
        # 2. Identify what exists on disk
        summaries_dir = PROJECT_ROOT / "memory" / "session_summaries_index"
        all_sessions = list(summaries_dir.rglob("session_*.json"))
        
        # 3. Find the delta
        to_scan = []
        for sess_path in all_sessions:
            rid = sess_path.stem.replace("session_", "")
            if rid not in scanned_ids:
                to_scan.append(sess_path)
        
        print(f"🧠 RemMe: Identified {len(to_scan)} pending sessions to scan.")
        
        # 4. Process matches (Newest First)
        to_scan.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        
        # Limit to avoid overloading on first boot if backlog is huge
        BATCH_SIZE = 100  # Process up to 100 sessions per sync
        
        from remme.extractor import RemmeExtractor
        extractor = RemmeExtractor()
        
        processed_count = 0
        
        for sess_path in to_scan[:BATCH_SIZE]:
            try:
                run_id = sess_path.stem.replace("session_", "")
                print(f"🧠 RemMe: Auto-Scanning Run {run_id}...")
                
                data = json.loads(sess_path.read_text(encoding="utf-8", errors="replace"))
                # Fix: Query is deeply nested in graph attributes for NetworkX adjacency format
                query = data.get("graph", {}).get("original_query", "")
                if not query:
                    # Fallback for older formats if any
                    query = data.get("query", "")
                
                # Reconstruct output
                nodes = data.get("nodes", [])
                output = ""
                for n in sorted(nodes, key=lambda x: x.get("id", "")):
                     if n.get("output"):
                         output = n.get("output")
                         
                if not query:
                    print(f"⚠️ RemMe: Run {run_id} has no query, marking as scanned and skipping.")
                    remme_store.mark_run_scanned(run_id)
                    continue

                hist = [{"role": "user", "content": query}]
                if output:
                    hist.append({"role": "assistant", "content": output})
                else:
                    # If no output, maybe it failed or is in progress. 
                    # We can still extract from query intent? No, usually need outcome.
                    # But user might want to remember they *tried* to do X.
                    pass

                # Search Context
                existing = []
                try:
                    emb = get_embedding(query, task_type="search_document")
                    existing = remme_store.search(query_vector=emb, query_text=query, k=5)
                except Exception:
                    pass
                
                # Extract memories (and preferences when legacy path)
                from memory.mnemo_config import is_mnemo_enabled
                extraction = None
                if is_mnemo_enabled():
                    from shared.state import get_unified_extractor
                    unified = get_unified_extractor()
                    extraction = await asyncio.to_thread(
                        unified.extract_from_session, query, hist, existing
                    )
                    print(f"🧠 RemMe: Extracted MEM from scanned Run {run_id}---->{extraction}")
                    commands = [{"action": m.action, "text": m.text, "id": m.id} for m in extraction.memories]
                    preferences = None
                else:
                    result = await asyncio.to_thread(extractor.extract, query, hist, existing)
                    if isinstance(result, tuple):
                        commands, preferences = result
                    else:
                        commands = result
                        preferences = {}
                
                session_memory_ids = []
                if commands:
                    for cmd in commands:
                        action = cmd.get("action")
                        text = cmd.get("text")
                        tid = cmd.get("id")
                        try:
                            if action == "add" and text:
                                emb = get_embedding(text, task_type="search_document")
                                added = remme_store.add(
                                    text, emb, category="derived", source=f"run_{run_id}",
                                    metadata={"session_id": run_id},
                                    skip_kg_ingest=is_mnemo_enabled(),
                                )
                                if added and isinstance(added, dict) and added.get("id"):
                                    session_memory_ids.append(added["id"])
                                processed_count += 1
                            elif action == "update" and tid and text:
                                emb = get_embedding(text, task_type="search_document")
                                remme_store.update(tid, text=text, embedding=emb)
                                processed_count += 1
                        except Exception as e:
                            print(f"❌ RemMe Action Failed: {e}")
                
                if is_mnemo_enabled() and extraction and session_memory_ids:
                    try:
                        from memory.knowledge_graph import get_knowledge_graph
                        from memory.user_id import get_user_id
                        kg = get_knowledge_graph()
                        if kg and kg.enabled:
                            user_id = get_user_id()
                            kg_result = kg.ingest_from_unified_extraction(
                                user_id, run_id, session_memory_ids, extraction,
                                category="derived", source="session",
                            )
                            entity_ids = kg_result.get("entity_ids", [])
                            entity_labels = kg_result.get("entity_labels", [])
                            if entity_ids or entity_labels:
                                meta = {"entity_ids": entity_ids}
                                if entity_labels:
                                    meta["entity_labels"] = entity_labels
                                for mid in session_memory_ids:
                                    remme_store.update(mid, metadata=meta)
                    except Exception as e:
                        print(f"⚠️ RemMe Neo4j session ingestion failed: {e}")
                
                if not is_mnemo_enabled() and preferences:
                    try:
                        from remme.staging import get_staging_store
                        staging = get_staging_store()
                        staging.add(preferences, source=f"session_{run_id}")
                        print(f"📥 Staged {len(preferences)} preferences for normalization")
                    except Exception as e:
                        print(f"⚠️ Failed to stage preferences: {e}")
                
                # Mark session as scanned
                remme_store.mark_run_scanned(run_id)
                
            except requests.exceptions.ConnectionError:
                print(f"⚠️ Ollama unreachable. Pausing Smart Scan for now.")
                break # Stop the loop, retry next time
            except Exception as e:
                print(f"❌ Failed to scan session {sess_path}: {e}")
                
        return processed_count

    except Exception as e:
        print(f"❌ Smart Scan Crashed: {e}")
        import traceback
        traceback.print_exc()
        return 0


# === Endpoints ===

@router.get("/memories")
async def get_memories(space_id: str | None = Query(None, description="Filter memories by space; omit for all")):
    """Get all stored memories with source existence check. Phase 4: optional space_id filter."""
    try:
        filter_meta = {"space_id": space_id} if space_id else None
        memories = remme_store.get_all(filter_metadata=filter_meta)
        summaries_dir = PROJECT_ROOT / "memory" / "session_summaries_index"
        
        # Add source_exists flag
        for m in memories:
            source = m.get("source", "")
            # Handle multiple sources in Hubs
            sources = [s.strip() for s in source.split(",")]
            exists = False
            for s in sources:
                # Handle various prefixes
                run_id = s
                for prefix in ["backfill_", "run_", "manual_scan_"]:
                    if run_id.startswith(prefix):
                        run_id = run_id.replace(prefix, "")
                        break
                
                if not run_id: continue
                
                # Brute force search for session file
                found = False
                for _ in summaries_dir.rglob(f"session_{run_id}.json"):
                    found = True
                    break
                if found:
                    exists = True
                    break
            
            # Special case: manual entries or no source
            if not source or source == "manual":
                exists = True 
            
            m["source_exists"] = exists
            
        return {"status": "success", "memories": memories}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cleanup_dangling")
async def cleanup_dangling_memories():
    """Delete all memories where the source session no longer exists"""
    try:
        memories = remme_store.get_all()
        summaries_dir = PROJECT_ROOT / "memory" / "session_summaries_index"
        ids_to_delete = []
        
        for m in memories:
            source = m.get("source", "")
            if not source or source == "manual": continue
            
            sources = [s.strip() for s in source.split(",")]
            exists = False
            for s in sources:
                run_id = s.replace("backfill_", "")
                if not run_id: continue
                for _ in summaries_dir.rglob(f"session_{run_id}.json"):
                    exists = True; break
                if exists: break
            
            if not exists:
                ids_to_delete.append(m["id"])
        
        for mid in ids_to_delete:
            remme_store.delete(mid)
            
        return {"status": "success", "deleted_count": len(ids_to_delete)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_memory(request: AddMemoryRequest, background_tasks: BackgroundTasks):
    """Manually add a memory. Optional space_id for Phase 3 Spaces. When MNEMO_ENABLED=false, auto-extract to UserModel hubs; when true, ingestion uses unified extractor. Phase 4: triggers background sync when sync engine enabled."""
    try:
        emb = get_embedding(request.text, task_type="search_query")
        add_kwargs: dict = {"category": request.category, "source": "manual"}
        if request.space_id:
            add_kwargs["space_id"] = request.space_id
        memory = remme_store.add(request.text, emb, **add_kwargs)

        from memory.mnemo_config import is_mnemo_enabled
        if not is_mnemo_enabled():
            try:
                from remme.bootstrap import extract_from_memories, apply_extraction_to_hubs
                print(f"🔄 Auto-extracting preferences from: '{request.text[:50]}...'")
                extraction = await extract_from_memories([{"text": request.text, "category": request.category}])
                if extraction:
                    changes = apply_extraction_to_hubs(extraction)
                    print(f"✅ Auto-extracted {len(changes)} preferences from new memory")
                    memory["extracted_preferences"] = changes
                else:
                    memory["extracted_preferences"] = []
            except Exception as e:
                print(f"⚠️ Auto-extraction failed (memory still saved): {e}")
                memory["extracted_preferences"] = []
        else:
            memory["extracted_preferences"] = []  # step 3 will ingest via unified extractor in qdrant_store

        # Phase 4: enqueue background sync when sync engine enabled
        try:
            from memory.sync_config import is_sync_engine_enabled, get_sync_server_url
            if is_sync_engine_enabled() and get_sync_server_url():
                from routers.sync import run_sync_background
                background_tasks.add_task(run_sync_background)
        except Exception:
            pass

        return {"status": "success", "memory": memory}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str):
    """Delete a memory"""
    try:
        remme_store.delete(memory_id)
        return {"status": "success", "id": memory_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/spaces")
async def create_space(request: CreateSpaceRequest, background_tasks: BackgroundTasks):
    """Create a new space for the user. Returns {space_id, name, description}. Phase 3 Spaces. Phase 4: triggers background sync when sync engine enabled."""
    try:
        from memory.knowledge_graph import get_knowledge_graph
        from memory.user_id import get_user_id
        kg = get_knowledge_graph()
        if not kg or not kg.enabled:
            raise HTTPException(status_code=503, detail="Neo4j not enabled")
        user_id = get_user_id()
        space_id = kg.create_space(
            user_id,
            name=request.name,
            description=request.description,
            sync_policy=request.sync_policy,
        )
        if not space_id:
            raise HTTPException(status_code=500, detail="Failed to create space")

        # Phase 4: enqueue background sync when sync engine enabled
        try:
            from memory.sync_config import is_sync_engine_enabled, get_sync_server_url
            if is_sync_engine_enabled() and get_sync_server_url():
                from routers.sync import run_sync_background
                background_tasks.add_task(run_sync_background)
        except Exception:
            pass

        return {"status": "success", "space_id": space_id, "name": request.name or "", "description": request.description or ""}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/spaces")
async def list_spaces():
    """List spaces owned by the user. Phase 3 Spaces."""
    try:
        from memory.knowledge_graph import get_knowledge_graph
        from memory.user_id import get_user_id
        kg = get_knowledge_graph()
        if not kg or not kg.enabled:
            return {"status": "success", "spaces": []}
        user_id = get_user_id()
        spaces = kg.get_spaces_for_user(user_id)
        return {"status": "success", "spaces": spaces}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/scan")
async def manual_remme_scan(background_tasks: BackgroundTasks):
    """Manually trigger RemMe Smart Sync."""
    print("🔎 RemMe: Manual Smart Scan Triggered")
    # We run this in background so UI returns immediately
    background_tasks.add_task(background_smart_scan)
    
    return {"status": "success", "message": "Smart Sync started in background. Check logs/UI updates."}


@router.get("/profile")
async def get_remme_profile():
    """Generates or retrieves a cached comprehensive user profile using Gemini."""
    try:
        REMME_INDEX_DIR = Path("memory/remme_index")
        profile_path = REMME_INDEX_DIR / "user_profile.md"
        
        # 1. Check Cache (Weekly)
        if profile_path.exists():
            modified_time = profile_path.stat().st_mtime
            current_time = datetime.now().timestamp()
            # 7 days in seconds = 604800
            if (current_time - modified_time) < 604800:
                print(f"🧠 RemMe Profile: Loading cached profile (Age: {(current_time - modified_time) / 86400:.1f} days)")
                return {"content": profile_path.read_text()}
                
        # 2. Generate New Profile
        print("🧠 RemMe Profile: Generating NEW profile via Gemini...")
        
        memories = remme_store.get_all()
        
        if not memories:
            return {"content": "# User Profile\n\nNo memories found yet. Engage with the AI to build your profile!"}
            
        memory_text = "\n".join([f"- {m['text']} (Category: {m.get('category', 'General')})" for m in memories])
        
        # 3. Load Preferences for styling and content
        try:
            from memory.mnemo_config import is_mnemo_enabled
            if is_mnemo_enabled():
                from memory.neo4j_preferences_adapter import build_preferences_from_neo4j
                from memory.user_id import get_user_id
                prefs_data = build_preferences_from_neo4j(get_user_id())
                if prefs_data:
                    prefs = prefs_data.get("preferences", {})
                    oc = prefs_data.get("operating_context", {})
                    soft = prefs_data.get("soft_identity", {})
                    meta = prefs_data.get("meta", {})
                    oc_out = prefs.get("output_contract", {})
                    interests = soft.get("interests_and_hobbies", {})
                    context_data = {
                        "tech_stack": {
                            "os": oc.get("os", "unknown"),
                            "shell": oc.get("shell", "unknown"),
                            "languages": oc.get("primary_languages", []),
                            "location": oc.get("location")
                        },
                        "output_contract": {
                            "verbosity": oc_out.get("verbosity", "detailed"),
                            "tones": oc_out.get("tone_constraints", []),
                            "avoid": prefs.get("anti_preferences", {})
                        },
                        "traits": soft.get("extras", {}),
                        "interests": {
                            "professional": interests.get("professional_interests", []),
                            "hobbies": interests.get("personal_hobbies", [])
                        },
                        "meta": {
                            "total_evidence": meta.get("total_evidence", 0),
                            "overall_confidence": meta.get("overall_confidence", 0.5)
                        }
                    }
                else:
                    context_data = {
                        "meta": {"overall_confidence": 0.5, "total_evidence": 0},
                        "output_contract": {"verbosity": "detailed", "tones": []},
                        "tech_stack": {"os": "unknown", "shell": "unknown", "languages": [], "location": None},
                        "traits": {},
                        "interests": {"professional": [], "hobbies": []}
                    }
            else:
                from remme.hubs.preferences_hub import get_preferences_hub
                from remme.hubs.operating_context_hub import get_operating_context_hub
                from remme.hubs.soft_identity_hub import get_soft_identity_hub
                prefs_hub = get_preferences_hub()
                context_hub = get_operating_context_hub()
                soft_hub = get_soft_identity_hub()
                context_data = {
                    "tech_stack": {
                        "os": context_hub.get_os(),
                        "shell": context_hub.get_shell(),
                        "languages": context_hub.get_primary_languages(),
                        "location": context_hub.data.environment.location_region.value
                    },
                    "output_contract": {
                        "verbosity": prefs_hub.get_verbosity(),
                        "tones": prefs_hub.get_tone_constraints(),
                        "avoid": prefs_hub.get_avoid_patterns()
                    },
                    "traits": getattr(soft_hub.data.meta, "traits", {}) if hasattr(soft_hub.data, "meta") else {},
                    "interests": {
                        "professional": soft_hub.data.interests_and_hobbies.professional_interests,
                        "hobbies": soft_hub.data.interests_and_hobbies.personal_hobbies
                    },
                    "meta": {
                        "total_evidence": (
                            prefs_hub.data.meta.evidence_count +
                            context_hub.data.meta.evidence_count +
                            soft_hub.data.meta.evidence_count
                        ),
                        "overall_confidence": max(
                            prefs_hub.data.meta.confidence,
                            context_hub.data.meta.confidence,
                            soft_hub.data.meta.confidence
                        )
                    }
                }
            
            # Format as readable block
            pref_block = f"""
USER CONTEXT & PREFERENCES:
- Operating Context: {context_data['tech_stack']['os']} with {context_data['tech_stack']['shell']}. Location: {context_data['tech_stack']['location']}
- Languages: {", ".join(context_data['tech_stack']['languages'])}
- Tone Preferences: {", ".join(context_data['output_contract']['tones'])}
- Target Verbosity: {context_data['output_contract']['verbosity']}
- Known Professional Interests: {", ".join(context_data['interests']['professional'])}
"""
        except Exception as e:
            print(f"⚠️ Failed to load preferences for profile prompt: {e}")
            pref_block = "No specific preferences or operating context detected yet."
            context_data = {
                "meta": {"overall_confidence": 0.5, "total_evidence": 0},
                "output_contract": {"verbosity": "detailed", "tones": ["Insightful", "Professional"]}
            }

        # Construct Prompt
        prompt = f"""
You are an expert psychological profiler and biographer. Your task is to create a DEEPLY DETAILED and CREATIVE Markdown profile of the user based on their memory fragments and discovered preferences.

**User Memories:**
{memory_text}

{pref_block}

---

**STYLE & FORMATTING INSTRUCTIONS (CRITICAL):**
1. **Respect the Tone**: If the user prefers a certain tone (e.g. witty, professional, punchy), ADAPT the entire report style to match.
2. **Respect Verbosity**: If the user wants '{context_data['output_contract']['verbosity'] if 'context_data' in locals() else 'detailed'}' output, ensure the length and detail level matches.
3. **Be Insightful**: Don't just list facts. Connect the dots. Why do they care about these specific technologies? What does their choice of shell or location say about their workflow?
4. **Gemini Oracle**: Use your 1M context foresight to predict their next move. If they are a Python developer in Bangalore working on agentic loops, what is the 'final boss' of their current project?
5. **Bold & Creative**: Use formatting (bolding, lists, blockquotes, horizontal rules) to make it a premium biographic document.

**Report Structure:**

# The User: A Comprehensive Psychological & Professional Profile
*Generated by Gemini 2.5 on {datetime.now().strftime('%B %d, %Y')}*

## 1. Executive Summary
A high-level overview of who the user appears to be, their primary drivers, and current state of mind.

## 2. Psychological Archetype (16 Personalities Prediction)
*   **Predicted Type:** (e.g. INTJ - The Architect)
*   **Cognitive Functions Analysis:** Based on how they ask questions (Te/Ti logic vs Fe/Fi values).
*   **Strengths & Weaknesses:** Derived from their interactions.

## 3. Professional & Intellectual Core
*   **Core Competencies:** What specific technologies, concepts, or domains do they master?
*   **Current Projects:** What are they working on right now? (Infer from recent queries).
*   **Learning Trajectory:** What are they trying to learn?

## 4. Interests & Passions
*   **Explicit Interests:** Things they asked about directly.
*   **Implicit Interests:** Deduced from side-comments or metaphors.
*   **Aesthetic Preferences:** (If any UI checks were made).

## 5. Creating Predictions (The "Gemini Oracle")
*   **Next Big Project:** Predict what they might build next.
*   **Potential Friends/Collaborators:** What kind of people would they form a "squad" with?
*   **Career Path 5-Year Prediction:** Where are they heading?

## 6. Cognitive Blindspots
*   What are they ignoring? What patterns do they repeat?

---

**Final Instruction**: Make this report feel like it was written by someone who *really* knows them. If they like humor, include jokes (perhaps about their tech stack or location). If they are strictly professional, be clinical and precise.
"""

        # Call model using user's selected provider from settings
        # Note: This is a token-heavy task - works best with large context models
        from config.settings_loader import reload_settings
        fresh_settings = reload_settings()
        agent_settings = fresh_settings.get("agent", {})
        model_provider = agent_settings.get("model_provider", "gemini")
        model_name = agent_settings.get("default_model", "gemini-2.5-flash")
        
        model_manager = ModelManager(model_name, provider=model_provider)
        profile_content = await model_manager.generate_text(prompt)
        
        # Save to Cache
        profile_path.write_text(profile_content)
        
        return {
            "content": profile_content,
            "confidence": context_data['meta']['overall_confidence'] if 'context_data' in locals() else 0.5,
            "evidence_count": context_data['meta']['total_evidence'] if 'context_data' in locals() else 0
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/preferences/facts")
async def update_fact(request: UpdateFactRequest):
    """Update or create a fact from UI (step 7). Requires MNEMO_ENABLED. Backend-ready; no UI changes yet."""
    try:
        from memory.mnemo_config import is_mnemo_enabled
        if not is_mnemo_enabled():
            raise HTTPException(
                status_code=501,
                detail="UI fact edits require MNEMO_ENABLED=true. Use legacy JSON hubs when disabled.",
            )
        from memory.user_id import get_user_id
        from memory.knowledge_graph import get_knowledge_graph
        kg = get_knowledge_graph()
        if not kg or not getattr(kg, "enabled", False):
            raise HTTPException(status_code=503, detail="Neo4j knowledge graph not available.")
        user_id = get_user_id()
        fid = kg.upsert_fact_from_ui(
            user_id=user_id,
            namespace=request.namespace,
            key=request.key,
            value_type=request.value_type,
            value=request.value,
            value_text=request.value_text,
            value_number=request.value_number,
            value_bool=request.value_bool,
            value_json=request.value_json,
            entity_ref=request.entity_ref,
            space_id=request.space_id,
        )
        if not fid:
            raise HTTPException(status_code=400, detail="Failed to upsert fact.")
        return {"status": "success", "fact_id": fid}
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preferences")
async def get_user_preferences(
    space_id: str | None = Query(None, description="Filter preferences to global + this space"),
    space_ids: str | None = Query(None, description="Comma-separated space IDs to include (alternative to space_id)"),
):
    """Get all UserModel preferences for frontend display. When MNEMO_ENABLED, reads from Neo4j via adapter; else from JSON hubs. Phase 3B: optional space_id/space_ids filter."""
    try:
        from memory.mnemo_config import is_mnemo_enabled
        if is_mnemo_enabled():
            from memory.neo4j_preferences_adapter import build_preferences_from_neo4j
            from memory.user_id import get_user_id
            space_ids_list = [s.strip() for s in (space_ids or "").split(",") if s.strip()] or None
            result = build_preferences_from_neo4j(
                get_user_id(),
                space_id=space_id,
                space_ids=space_ids_list,
            )
            if result:
                return result

        from remme.hubs.preferences_hub import get_preferences_hub
        from remme.hubs.operating_context_hub import get_operating_context_hub
        from remme.hubs.soft_identity_hub import get_soft_identity_hub
        from remme.engines.evidence_log import get_evidence_log

        prefs_hub = get_preferences_hub()
        context_hub = get_operating_context_hub()
        soft_hub = get_soft_identity_hub()
        evidence_log = get_evidence_log()
        
        # Get soft identity data with full detail
        soft_data = soft_hub.data
        
        return {
            "status": "success",
            "preferences": {
                # Output Contract
                "output_contract": {
                    "verbosity": prefs_hub.get_verbosity(),
                    "format": prefs_hub.get_format(),
                    "tone_constraints": prefs_hub.get_tone_constraints(),
                    "structure_rules": prefs_hub.get_structure_rules(),
                    "clarifications": prefs_hub.get_clarifications_policy(),
                },
                # Anti-preferences
                "anti_preferences": prefs_hub.get_avoid_patterns(),
                # Tooling
                "tooling": prefs_hub.get_tooling_defaults(),
                # Autonomy
                "autonomy": {
                    "create_files": prefs_hub.get_autonomy("create_files"),
                    "run_shell": prefs_hub.get_autonomy("run_shell"),
                    "delete_files": prefs_hub.get_autonomy("delete_files"),
                    "git_operations": prefs_hub.get_autonomy("git_operations"),
                },
                "risk_tolerance": prefs_hub.get_risk_tolerance(),
            },
            "operating_context": {
                "os": context_hub.get_os(),
                "shell": context_hub.get_shell(),
                "cpu_architecture": context_hub.get_cpu_architecture(),
                "primary_languages": context_hub.get_primary_languages(),
                "has_gpu": context_hub.has_gpu(),
                "assumption_limits": context_hub.get_assumption_limits(),
                "location": context_hub.data.environment.location_region.value,
            },
            "soft_identity": {
                # Discovered Traits (Extras) - Keep as objects with confidence
                "extras": soft_data.extras if hasattr(soft_data, "extras") else {},
                
                # Food & Dining
                "food_and_dining": {
                    "dietary_style": soft_data.food_and_dining.dietary_style.value,
                    "cuisine_likes": soft_data.food_and_dining.cuisine_affinities.likes,
                    "cuisine_dislikes": soft_data.food_and_dining.cuisine_affinities.dislikes,
                    "favorite_foods": soft_data.food_and_dining.cuisine_affinities.favorites,
                    "food_allergies": soft_data.food_and_dining.restrictions.allergies,
                },
                # Pets
                "pets_and_animals": {
                    "affinity": soft_data.pets_and_animals.affinity.value,
                    "pet_names": soft_data.pets_and_animals.ownership.pet_names,
                },
                # Lifestyle
                "lifestyle_and_wellness": {
                    "activity_level": soft_data.lifestyle_and_wellness.activity_level.value,
                    "sleep_rhythm": soft_data.lifestyle_and_wellness.sleep_rhythm.value,
                    "travel_style": soft_data.lifestyle_and_wellness.travel_style.value,
                },
                # Media
                "media_and_entertainment": {
                    "music_genres": soft_data.media_and_entertainment.music.genres,
                    "movie_genres": soft_data.media_and_entertainment.movies_tv.genres,
                    "book_genres": soft_data.media_and_entertainment.books.genres,
                    "podcast_genres": soft_data.media_and_entertainment.podcasts.genres,
                },
                # Communication
                "communication_style": {
                    "humor_tolerance": soft_data.communication_style.humor_tolerance.value,
                    "small_talk_tolerance": soft_data.communication_style.small_talk_tolerance.value,
                    "formality_preference": soft_data.communication_style.formality_preference.value,
                },
                # Interests
                "interests_and_hobbies": {
                    "professional_interests": soft_data.interests_and_hobbies.professional_interests,
                    "personal_hobbies": soft_data.interests_and_hobbies.personal_hobbies,
                    "learning_interests": soft_data.interests_and_hobbies.learning_interests,
                    "side_projects": soft_data.interests_and_hobbies.side_projects,
                },
                # Professional
                "professional_context": {
                    "industry": soft_data.professional_context.industry.value,
                    "role_type": soft_data.professional_context.role_type.value,
                    "experience_level": soft_data.professional_context.experience_level.value,
                    "team_size": soft_data.professional_context.team_size.value,
                },
            },
            "evidence": {
                "total_events": len(evidence_log.data.events),
                "events_by_source": dict(evidence_log.data.meta.events_by_source),
                "events_by_type": dict(evidence_log.data.meta.events_by_type),
            },
            "meta": {
                "preferences_confidence": prefs_hub.data.meta.confidence,
                "preferences_evidence_count": prefs_hub.data.meta.evidence_count,
                "context_confidence": context_hub.data.meta.confidence,
                "soft_identity_confidence": soft_hub.data.meta.confidence,
                "total_evidence": (
                    prefs_hub.data.meta.evidence_count + 
                    context_hub.data.meta.evidence_count + 
                    soft_hub.data.meta.evidence_count
                ),
                "overall_confidence": max(
                    prefs_hub.data.meta.confidence,
                    context_hub.data.meta.confidence,
                    soft_hub.data.meta.confidence
                )
            }
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        # Return empty/default structure on error
        return {
            "status": "error",
            "error": str(e),
            "preferences": {},
            "operating_context": {},
            "soft_identity": {},
            "evidence": {},
            "meta": {}
        }


@router.post("/preferences/bootstrap")
async def bootstrap_preferences():
    """Bootstrap UserModel hubs from existing REMME memories using LLM extraction."""
    try:
        from remme.bootstrap import bootstrap_from_remme
        
        print("🚀 Starting preferences bootstrap...")
        changes = await bootstrap_from_remme()
        
        return {
            "status": "success",
            "message": f"Bootstrapped {len(changes)} preference fields from memories",
            "changes": changes
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e),
            "changes": []
        }


@router.get("/staging/status")
async def get_staging_status():
    """Get status of the preference staging queue."""
    try:
        from remme.staging import get_staging_store
        
        staging = get_staging_store()
        
        return {
            "status": "success",
            "pending_count": staging.get_pending_count(),
            "should_normalize": staging.should_normalize(),
            "last_normalized": staging.data.get("last_normalized"),
            "pending_preview": staging.get_pending()[:5]  # First 5 items
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "pending_count": 0
        }


@router.post("/normalize")
async def run_normalize():
    """Run the normalizer to process pending preferences from staging."""
    try:
        from remme.normalizer import run_normalizer
        
        print("🔄 Running preference normalizer...")
        changes = await run_normalizer()
        
        return {
            "status": "success",
            "message": f"Normalized and applied {len(changes)} preferences",
            "changes": changes
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e),
            "changes": []
        }


@router.post("/scan/system")
async def run_system_scan():
    """
    Run system-wide preference scan across ALL sources:
    - Notes folder
    - Session summaries
    - Then normalize and apply to hubs
    """
    try:
        from remme.sources.notes_scanner import scan_notes
        from remme.sources.session_scanner import scan_sessions
        from remme.normalizer import run_normalizer
        
        print("🔍 Starting SYSTEM-WIDE preference scan...")
        
        # 1. Scan Notes
        notes_count = await scan_notes()
        
        # 2. Scan Sessions
        sessions_count = await scan_sessions()
        
        # 3. Run normalizer on all staged preferences
        changes = await run_normalizer()
        
        return {
            "status": "success",
            "message": f"System scan complete",
            "notes_scanned": notes_count,
            "sessions_scanned": sessions_count,
            "preferences_normalized": len(changes),
            "changes": changes
        }
    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "error": str(e)
        }


@router.post("/scan/notes")
async def run_notes_scan():
    """Scan Notes folder for preferences."""
    try:
        from remme.sources.notes_scanner import scan_notes
        
        print("📝 Scanning Notes folder...")
        count = await scan_notes()
        
        return {
            "status": "success",
            "message": f"Scanned notes, found preferences in {count} files"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


@router.post("/scan/sessions")
async def run_sessions_scan():
    """Scan session summaries for preferences."""
    try:
        from remme.sources.session_scanner import scan_sessions
        
        print("💬 Scanning session summaries...")
        count = await scan_sessions()
        
        return {
            "status": "success",
            "message": f"Scanned sessions, found preferences in {count} sessions"
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
