# Explorer Router - File system scanning, code analysis, and architecture mapping
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import os
import json
import shutil
import tempfile
import subprocess
from pathlib import Path

# Import agents/tools
from core.explorer_utils import CodeSkeletonExtractor
from core.model_manager import ModelManager


router = APIRouter()

class AnalyzeRequest(BaseModel):
    path: str
    type: str = "local"  # local, github
    files: Optional[List[str]] = None

@router.get("/explorer/scan")
async def scan_project_files(path: str):
    """Scan project files for the context selector"""
    try:
        abs_path = path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
            
        if not os.path.exists(abs_path):
            raise HTTPException(status_code=404, detail="Path not found")
            
        extractor = CodeSkeletonExtractor(abs_path)
        scan_results = extractor.scan_project()
        
        return {
            "success": True,
            "scan": scan_results,
            "root_path": abs_path
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system/files")
async def list_files(path: str):
    """Recursively list files for the explorer panel"""
    try:
        abs_path = path
        if not os.path.isabs(abs_path):
            abs_path = os.path.abspath(abs_path)
            
        print(f"📁 Explorer: Listing files for {abs_path}")
            
        if not os.path.exists(abs_path):
            print(f"  ⚠️ Path not found: {abs_path}")
            return { "files": [], "root_path": abs_path, "error": "Path not found" }
        
        extractor = CodeSkeletonExtractor(abs_path)
        
        def build_tree(current_path):
            nodes = []
            try:
                items = os.listdir(current_path)
            except (PermissionError, FileNotFoundError):
                return []
                
            for item in items:
                full_path = os.path.join(current_path, item)
                try:
                    if extractor.is_ignored(full_path):
                        print(f"    - Ignored: {item}")
                        continue
                    
                    print(f"    + Found: {item} ({'folder' if os.path.isdir(full_path) else 'file'})")
                    node = {
                        "name": item,
                        "path": full_path,
                        "type": "folder" if os.path.isdir(full_path) else "file"
                    }
                    if os.path.isdir(full_path):
                        children = build_tree(full_path)
                        if children:
                            node["children"] = children
                    nodes.append(node)
                except Exception as e:
                    print(f"    ⚠️ Error processing {item}: {e}")
                    continue
            
            nodes.sort(key=lambda x: (x["type"] != "folder", x["name"].lower()))
            return nodes

        return {
            "files": build_tree(abs_path),
            "root_path": abs_path
        }
    except Exception as e:
        print(f"  ❌ List Files Failed: {e}")
        return { "files": [], "root_path": path, "error": str(e) }


@router.post("/explorer/analyze")
async def analyze_project(request: AnalyzeRequest):
    """Analyze a project and generate an architecture map"""
    target_path = request.path
    is_temp = False
    print(f"🧠 Explorer: Analyzing {target_path} (Type: {request.type})")
    
    try:
        # 1. HANDLE GITHUB
        if request.type == "github" or target_path.startswith("http"):
            is_temp = True
            temp_dir = tempfile.mkdtemp()
            print(f"  🔗 Cloning GitHub Repo {target_path} to {temp_dir}...")
            try:
                # Add --depth 1 for speed
                subprocess.run(["git", "clone", "--depth", "1", target_path, temp_dir], check=True, capture_output=True)
                target_path = temp_dir
                print("  ✅ Clone Successful.")
            except subprocess.CalledProcessError as e:
                err_msg = e.stderr.decode() if e.stderr else str(e)
                print(f"  ❌ Clone Failed: {err_msg}")
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                raise HTTPException(status_code=400, detail=f"Git clone failed: {err_msg}")
        else:
            # Resolve local path
            target_path = os.path.abspath(target_path)
            if not os.path.exists(target_path):
                print(f"  ⚠️ Local path not found: {target_path}")
                raise HTTPException(status_code=404, detail=f"Local path not found: {target_path}")

        if request.files:
            # Context Analysis Mode: We have a selected list of files
            # Read full content of selected files
            print(f"  📚 Analying {len(request.files)} selected files with Full Context...")
            context_str = ""
            for rel_path in request.files:
                full_path = os.path.join(target_path, rel_path)
                try:
                    with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                        context_str += f"--- FILE: {rel_path} ---\n{content}\n\n"
                except Exception as e:
                    print(f"  ⚠️ Could not read {rel_path}: {e}")
        else:
            # Fallback to Skeleton Mode (Legacy/Auto)
            # 2. EXTRACT SKELETON
            print("  💀 Extracting Skeletons (Blind Mode)...")
            extractor = CodeSkeletonExtractor(target_path)
            skeletons = extractor.extract_all()
            
            # Combine into a single prompt context
            context_str = ""
            for file_path, skel in skeletons.items():
                context_str += f"--- FILE: {file_path} ---\n{skel}\n\n"
        
        if not context_str:
            raise HTTPException(status_code=400, detail="No content found in the specified path/files for analysis.")

        # 3. LLM ANALYSIS
        model = ModelManager("gemini")
        prompt = f"""
        You are an elite software architect. Analyze the following code skeleton and generate a high-level architecture map in FlowStep format.
        
        CODE CONTEXT:
        {context_str}
        
        GOAL:
        1. Identify the core logical components (Manager classes, API layers, UI components, Utilities).
        2. Group related functionality into thematic blocks.
        3. Map how data flows between these components.
        
        OUTPUT FORMAT (JSON ONLY):
        {{
            "nodes": [
                {{ 
                    "id": "1", 
                    "type": "agent", 
                    "position": {{ "x": 250, "y": 0 }}, 
                    "data": {{ 
                        "label": "ComponentName", 
                        "description": "Short explanation of what this component does.",
                        "details": ["Key Function A", "Key class B"], 
                        "attributes": ["Async", "Priority: High", "Stateful"]
                    }} 
                }}
            ],
            "edges": [
                {{ "id": "e1-2", "source": "1", "target": "2", "type": "smoothstep" }}
            ],
            "sequence": ["1", "2"]
        }}
        
        LAYOUT RULES:
        - Increment Y by ~250 for each layer to create a vertical flow.
        - X should be around 250 for center, or +/- 200 for side-branches.

        Be technical and precise. Focus on architectural intent.
        """
        
        response_text = await model.generate_text(prompt)
        print(f"  🤖 LLM Response (Raw): {response_text[:200]}...")
        
        # Clean response if it contains markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
            
        try:
            flow_data = json.loads(response_text)
        except json.JSONDecodeError as je:
            print(f"  ❌ JSON Parse Error: {je}")
            raise HTTPException(status_code=500, detail=f"LLM returned invalid JSON: {str(je)}")
            
        return {
            "success": True, 
            "flow_data": flow_data,
            "root_path": request.path if (request.type == "github" or request.path.startswith("http")) else target_path
        }
        
    except Exception as e:
        print(f"Analysis Failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if is_temp and os.path.exists(target_path):
            shutil.rmtree(target_path)
