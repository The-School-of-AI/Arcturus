
import unittest
import ast
import sys
import os
sys.path.append(os.getcwd())
from core.mcp_inspector import MCPInspector

class TestMCPInspector(unittest.TestCase):
    def test_inspect_source_basic(self):
        source = """
def my_tool(arg1: str, arg2: int):
    \"\"\"
    My tool description.
    \"\"\"
    pass
"""
        tools = MCPInspector.inspect_source(source)
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool["name"], "my_tool")
        self.assertEqual(tool["description"], "My tool description.")
        self.assertEqual(tool["inputSchema"]["properties"]["arg1"]["type"], "string")
        self.assertEqual(tool["inputSchema"]["properties"]["arg2"]["type"], "integer")
        self.assertEqual(tool["inputSchema"]["required"], ["arg1", "arg2"])

    def test_inspect_source_defaults(self):
        source = """
def tool_with_defaults(req: str, opt: str = "default"):
    \"\"\"Description.\"\"\"
    pass
"""
        tools = MCPInspector.inspect_source(source)
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool["inputSchema"]["required"], ["req"])
        self.assertNotIn("opt", tool["inputSchema"]["required"])

    def test_inspect_source_complex_types(self):
        source = """
from typing import List, Optional, Dict

def complex_tool(
    items: List[str], 
    options: Dict[str, Any], 
    flag: Optional[bool] = None
):
    \"\"\"Complex tool.\"\"\"
    pass
"""
        tools = MCPInspector.inspect_source(source)
        self.assertEqual(len(tools), 1)
        props = tools[0]["inputSchema"]["properties"]
        
        self.assertEqual(props["items"]["type"], "array")
        # Dict is mapped to object
        self.assertEqual(props["options"]["type"], "object")
        # Optional[bool] -> boolean
        self.assertEqual(props["flag"]["type"], "boolean")

    def test_sandbox_tool_signature(self):
        # Mimic tools/sandbox.py signature
        source = """
async def run_user_code(code: str, multi_mcp, session_id: str = "default_session") -> dict:
    \"\"\"Execute user code.\"\"\"
    pass
"""
        tools = MCPInspector.inspect_source(source)
        self.assertEqual(len(tools), 1)
        tool = tools[0]
        self.assertEqual(tool["name"], "run_user_code")
        props = tool["inputSchema"]["properties"]
        self.assertEqual(props["code"]["type"], "string")
        self.assertEqual(props["multi_mcp"]["type"], "string") # Fallback
        self.assertEqual(props["session_id"]["type"], "string")
        self.assertEqual(tool["inputSchema"]["required"], ["code", "multi_mcp"])

if __name__ == "__main__":
    unittest.main()
