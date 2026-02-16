
import unittest
import sys
import os
sys.path.append(os.getcwd())
from pydantic import ValidationError
from core.tool_schema import validate_tool_definition, InvalidToolDefinition, ToolDefinition

class TestToolSchema(unittest.TestCase):
    def test_valid_tool(self):
        data = {
            "name": "my_tool",
            "description": "Valid description",
            "inputSchema": {
                "type": "object",
                "properties": {"arg": {"type": "string"}},
                "required": ["arg"]
            }
        }
        tool = validate_tool_definition(data)
        self.assertIsInstance(tool, ToolDefinition)
        self.assertEqual(tool.name, "my_tool")

    def test_missing_description(self):
        data = {
            "name": "bad_tool",
            # "description": Missing
            "inputSchema": {"type": "object", "properties": {}}
        }
        with self.assertRaises(InvalidToolDefinition):
            validate_tool_definition(data)

    def test_empty_description(self):
        data = {
            "name": "bad_tool",
            "description": "   ", # Empty/Whitespace
            "inputSchema": {"type": "object", "properties": {}}
        }
        with self.assertRaises(InvalidToolDefinition):
            validate_tool_definition(data)

    def test_invalid_schema_type(self):
        data = {
            "name": "bad_tool",
            "description": "desc",
            "inputSchema": "not_a_dict" # Invalid type
        }
        with self.assertRaises(InvalidToolDefinition):
            validate_tool_definition(data)

if __name__ == "__main__":
    unittest.main()
