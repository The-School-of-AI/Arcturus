# RemMe Router - Handles memory management, smart scan, and user profile
import asyncio
import json
from pathlib import Path
from datetime import datetime
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

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
                
                data = json.loads(sess_path.read_text())
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
                    existing = remme_store.search(query, limit=5)
                except:
                    pass
                
                # Extract
                commands = await asyncio.to_thread(extractor.extract, query, hist, existing)
                
                # Apply
                if commands:
                    for cmd in commands:
                        action = cmd.get("action")
                        text = cmd.get("text")
                        tid = cmd.get("id")
                        
                        try:
                            if action == "add" and text:
                                emb = get_embedding(text, task_type="search_document")
                                # Mark source as the run_id so we don't scan again
                                remme_store.add(text, emb, category="derived", source=f"run_{run_id}")
                                processed_count += 1
                            elif action == "update" and tid and text:
                                emb = get_embedding(text, task_type="search_document")
                                remme_store.update_text(tid, text, emb)
                                processed_count += 1
                        except Exception as e:
                            print(f"❌ RemMe Action Failed: {e}")
                
                # If no commands generated, we still need to mark it as scanned?
                # YES - we now use an explicit tracking file.
                remme_store.mark_run_scanned(run_id)
                
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
async def get_memories():
    """Get all stored memories with source existence check"""
    try:
        memories = remme_store.get_all()
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
async def add_memory(request: AddMemoryRequest):
    """Manually add a memory"""
    try:
        emb = get_embedding(request.text, task_type="search_query")
        memory = remme_store.add(request.text, emb, category=request.category, source="manual")
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
        
        # Load all memories
        if not remme_store.index:
            remme_store.load_index()
            
        memories = remme_store.get_all()
        
        if not memories:
            return {"content": "# User Profile\n\nNo memories found yet. Engage with the AI to build your profile!"}
            
        memory_text = "\n".join([f"- {m['text']} (Category: {m.get('category', 'General')})" for m in memories])
        
        # Construct Prompt
        prompt = f"""
You are an expert psychological profiler and biographer. Your task is to create a DEEPLY DETAILED and CREATIVE Markdown profile of the user based on their memory fragments.

**User Memories:**
{memory_text}

---

**Instructions:**
Create a comprehensive Markdown report (at least 2000-3000 words logic, but keep it structured). 
Be extremely creative, insightful, and make bold predictions.

**Report Structure:**

# 👤 The User: A Comprehensive Psychological & Professional Profile
*Generated by Gemini 2.0 on {datetime.now().strftime('%B %d, %Y')}*

## 1. Executive Summary
A high-level overview of who the user appears to be, their primary drivers, and current state of mind.

## 2. 🧠 Psychological Archetype (16 Personalities Prediction)
*   **Predicted Type:** (e.g. INTJ - The Architect)
*   **Cognitive Functions Analysis:** Based on how they ask questions (Te/Ti logic vs Fe/Fi values).
*   **Strengths & Weaknesses:** Derived from their interactions.

## 3. 💼 Professional & Intellectual Core
*   **Core Competencies:** What specific technologies, concepts, or domains do they master?
*   **Current Projects:** What are they working on right now? (Infer from recent queries).
*   **Learning Trajectory:** What are they trying to learn?

## 4. ❤️ Interests & Passions
*   **Explicit Interests:** Things they asked about directly.
*   **Implicit Interests:** Deduced from side-comments or metaphors.
*   **Aesthetic Preferences:** (If any UI checks were made).

## 5. 🔮 Creating Predictions (The "Gemini Oracle")
*   **Next Big Project:** Predict what they might build next.
*   **Potential Friends/Collaborators:** What kind of people would they form a "squad" with?
*   **Career Path 5-Year Prediction:** Where are they heading?

## 6. ⚠️ Cognitive Blindspots
*   What are they ignoring? What patterns do they repeat?

---

**Style:** Professional yet engaging, slightly witty, and very insightful. Use formatting (bolding, lists, blockquotes) effectively.
"""

        # Call Gemini (using default configured model or explicit gemini-2.5-flash if needed)
        # Using ModelManager to handle the call
        model_manager = ModelManager("gemini") # Force Gemini for this token-heavy task
        profile_content = await model_manager.generate_text(prompt)
        
        # Save to Cache
        profile_path.write_text(profile_content)
        
        return {"content": profile_content}
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
