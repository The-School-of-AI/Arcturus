"""
Tests Router - Manages generated tests for the Arcturus IDE.
Handles test manifest, test generation triggers, and test execution.
"""
import os
import json
import sys
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict

# Add project root to path to allow importing tools and agents
sys.path.append(str(Path(__file__).parent.parent))
from tools.ast_differ import analyze_file, FileAnalysis
from agents.base_agent import AgentRunner

router = APIRouter(prefix="/tests", tags=["tests"])

# ... (Models and Helpers remain same)

# ... (Endpoints)

# =============================================================================
# Models
# =============================================================================

class TestItem(BaseModel):
    id: str
    name: str
    status: str  # 'passing' | 'failing' | 'stale' | 'orphaned' | 'pending'
    type: str    # 'behavior' | 'spec'
    lastRun: Optional[str] = None


class FileTests(BaseModel):
    file: str
    tests: List[TestItem]


class GenerateTestsRequest(BaseModel):
    path: str
    file_path: str
    function_names: Optional[List[str]] = None
    test_type: str = "behavior"  # 'behavior' or 'spec'
    force: bool = False # If true, ignore semantic hashing check


class RunTestsRequest(BaseModel):
    path: str
    test_ids: List[str]


# =============================================================================
# Helpers
# =============================================================================

def get_arcturus_tests_dir(project_root: str) -> Path:
    """Get the .arcturus/tests directory for a project."""
    tests_dir = Path(project_root) / ".arcturus" / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    return tests_dir


def get_manifest_path(project_root: str) -> Path:
    """Get the path to the test manifest file."""
    return get_arcturus_tests_dir(project_root) / "manifest.json"


def load_manifest(project_root: str) -> Dict:
    """Load the test manifest, creating empty one if it doesn't exist."""
    manifest_path = get_manifest_path(project_root)
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def save_manifest(project_root: str, manifest: Dict):
    """Save the test manifest."""
    manifest_path = get_manifest_path(project_root)
    manifest_path.write_text(json.dumps(manifest, indent=2))


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/manifest")
async def get_manifest(path: str):
    """Get the full test manifest for a project."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    manifest = load_manifest(path)
    return {"manifest": manifest}


@router.get("/for-file")
async def get_tests_for_file(path: str, file_path: str):
    """Get all tests associated with a specific source file."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    manifest = load_manifest(path)
    file_data = manifest.get(file_path, {})
    
    tests = []
    
    # Check if file has changed semantically since last generation
    has_changes = False
    try:
        abs_file_path = os.path.join(path, file_path) if not file_path.startswith('/') else file_path
        if os.path.exists(abs_file_path):
            analysis = analyze_file(abs_file_path)
            if analysis:
                current_hash = analysis.file_hash
                stored_hash = file_data.get("file_hash")
                if current_hash != stored_hash:
                    has_changes = True
    except Exception as e:
        print(f"Error checking file changes: {e}")

    for func_name, func_data in file_data.get("functions", {}).items():
        for test_id in func_data.get("tests", []):
            status = func_data.get("status", "pending")
            # Mark as stale if file changed
            if has_changes:
                status = "stale"
                
            tests.append({
                "id": test_id,
                "name": test_id.replace("test_", "").replace("_", " ").title(),
                "status": status,
                "type": func_data.get("type", "behavior"),
                "lastRun": func_data.get("last_run")
            })
    
    return {"tests": tests, "file": file_path, "has_changes": has_changes}


@router.post("/generate")
async def generate_tests(request: GenerateTestsRequest):
    """
    Trigger test generation for functions in a file using AST analysis.
    Only generates tests for modified functions unless forced.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    manifest = load_manifest(request.path)
    
    abs_file_path = os.path.join(request.path, request.file_path) if not request.file_path.startswith('/') else request.file_path
    
    if not os.path.exists(abs_file_path):
        raise HTTPException(status_code=404, detail=f"Source file not found: {request.file_path}")

    # Analyze file
    analysis = analyze_file(abs_file_path)
    if not analysis:
        raise HTTPException(status_code=500, detail="Failed to analyze source file")
        
    # Initialize file entry if needed
    if request.file_path not in manifest:
        manifest[request.file_path] = {
            "tests": [],
            "functions": {},
            "last_generated": None,
            "file_hash": None
        }
        
    file_entry = manifest[request.file_path]
    
    # Identify changed functions
    functions_to_process = []
    
    if request.force:
        functions_to_process = list(analysis.functions.keys())
        for class_name, methods in analysis.classes.items():
            for method_name in methods:
                 functions_to_process.append(f"{class_name}.{method_name}")
    else:
        # Compare hashes
        for func_name, info in analysis.functions.items():
            stored_info = file_entry["functions"].get(func_name, {})
            if stored_info.get("body_hash") != info.body_hash:
                functions_to_process.append(func_name)
                # Update stored info
                if func_name not in file_entry["functions"]:
                    file_entry["functions"][func_name] = {}
                file_entry["functions"][func_name]["body_hash"] = info.body_hash

        for class_name, methods in analysis.classes.items():
            for method_name, info in methods.items():
                full_name = f"{class_name}.{method_name}"
                stored_info = file_entry["functions"].get(full_name, {})
                if stored_info.get("body_hash") != info.body_hash:
                    functions_to_process.append(full_name)
                    if full_name not in file_entry["functions"]:
                        file_entry["functions"][full_name] = {}
                    file_entry["functions"][full_name]["body_hash"] = info.body_hash

    # Save manifest updates
    file_entry["file_hash"] = analysis.file_hash
    file_entry["last_generated"] = datetime.now().isoformat()
    save_manifest(request.path, manifest)
    
    if not functions_to_process:
        return {
            "success": True,
            "message": "No semantic changes detected. No tests generated.",
            "functions": []
        }

    # Invoke Test Agent
    try:
        # read source code
        with open(abs_file_path, 'r') as f:
            source_code = f.read()

        runner = AgentRunner(multi_mcp=None) # No MCP needed for TestAgent
        input_data = {
            "source_code": source_code,
            "existing_tests": "", # TODO: Load existing tests if updating
            "context": f"Project: {os.path.basename(request.path)}. Analyzing file: {request.file_path}"
        }
        
        # Run agent
        result = await runner.run_agent("TestAgent", input_data)
        
        # Save generated tests
        # Assuming result contains code block. We might need parsing.
        # For now, we save raw response to a temporary file or specific test file.
        test_filename = f"test_{Path(request.file_path).name}"
        test_path = get_arcturus_tests_dir(request.path) / test_filename
        
        # Append or write? Best to write fresh if focusing on unit.
        # But we generated for specific functions? 
        # Ideally we merge. For now, overwrite/append.
        
        # Simple extraction of code block
        code = result
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
            
        test_path.write_text(code)
        
        return {
            "success": True,
            "message": f"Generated tests for {len(functions_to_process)} functions",
            "changed_functions": functions_to_process,
            "test_file": str(test_path)
        }
        
    except Exception as e:
        print(f"Test Agent failed: {e}")
        raise HTTPException(status_code=500, detail=f"Test generation failed: {str(e)}")


@router.post("/generate-spec")
async def generate_spec_tests(request: GenerateTestsRequest):
    """
    Generate spec-based tests from docstrings and comments.
    This is triggered manually by the user.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    abs_file_path = os.path.join(request.path, request.file_path) if not request.file_path.startswith('/') else request.file_path
    
    if not os.path.exists(abs_file_path):
        raise HTTPException(status_code=404, detail=f"Source file not found: {request.file_path}")

    # Invoke Test Agent for Spec Generation
    try:
        # read source code
        with open(abs_file_path, 'r') as f:
            source_code = f.read()

        runner = AgentRunner(multi_mcp=None)
        input_data = {
            "source_code": source_code,
            "existing_tests": "", 
            "context": f"Project: {os.path.basename(request.path)}. Analyzing file: {request.file_path}\n"
                       f"TASK: Generate SPEC TESTS. Strictly test against the contracts defined in docstrings, type hints, and comments. "
                       f"Do not test implementation details not promised in the spec."
        }
        
        # Run agent
        result = await runner.run_agent("TestAgent", input_data)
        
        # Save generated tests
        test_filename = f"test_{Path(request.file_path).name.replace('.py', '_spec.py')}"
        test_path = get_arcturus_tests_dir(request.path) / test_filename
        
        code = result
        if "```python" in code:
            code = code.split("```python")[1].split("```")[0].strip()
        elif "```" in code:
            code = code.split("```")[1].split("```")[0].strip()
            
        test_path.write_text(code)
        
        return {
            "success": True,
            "message": f"Spec tests generated at {test_filename}",
            "test_file": str(test_path),
            "test_type": "spec"
        }
        
    except Exception as e:
        print(f"Test Agent failed: {e}")
        raise HTTPException(status_code=500, detail=f"Spec test generation failed: {str(e)}")


@router.put("/activate")
async def toggle_test_activation(path: str, file_path: str, test_id: str, active: bool):
    """Toggle whether a test is active (will be run)."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    manifest = load_manifest(path)
    
    if file_path not in manifest:
        manifest[file_path] = {"tests": [], "functions": {}}
    
    # Find and update the test
    for func_name, func_data in manifest[file_path].get("functions", {}).items():
        if test_id in func_data.get("tests", []):
            if "active" not in func_data:
                func_data["active"] = []
            
            if active and test_id not in func_data["active"]:
                func_data["active"].append(test_id)
            elif not active and test_id in func_data["active"]:
                func_data["active"].remove(test_id)
    
    save_manifest(path, manifest)
    
    return {"success": True, "test_id": test_id, "active": active}


@router.post("/run")
async def run_tests(request: RunTestsRequest):
    """
    Run the specified tests using pytest.
    Returns results after execution.
    """
    if not os.path.exists(request.path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    # TODO: Implement actual pytest execution
    # For now, return a placeholder response
    
    results = []
    for test_id in request.test_ids:
        results.append({
            "test_id": test_id,
            "status": "pending",
            "message": "Test execution not yet implemented"
        })
    
    return {
        "success": True,
        "results": results,
        "total": len(request.test_ids),
        "passed": 0,
        "failed": 0
    }


@router.get("/results")
async def get_test_results(path: str, file_path: Optional[str] = None):
    """Get the latest test results for a project or specific file."""
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Path not found")
    
    # TODO: Read from pytest output/cache
    
    return {
        "results": [],
        "last_run": None,
        "summary": {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0
        }
    }
