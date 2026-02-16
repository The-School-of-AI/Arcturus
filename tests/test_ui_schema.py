
import unittest
import sys
import os
import json
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.schemas.ui_schema import validate_ui_json

class TestUISchema(unittest.TestCase):
    def test_ui_validation(self):
        ui_data = {
            "name": "Arcturus Portfolio",
            "version": "1.0.0",
            "theme": {
                "colors": {
                    "primary": "#00f2fe",
                    "secondary": "#4facfe"
                },
                "glassmorphism": True
            },
            "pages": [
                {
                    "title": "Home",
                    "path": "/",
                    "components": [
                        {
                            "id": "hero-1",
                            "type": "hero",
                            "title": "The Infinite Agentic OS",
                            "content": {
                                "subtitle": "Arcturus is the next step in human-AI collaboration.",
                                "cta": "Get Started"
                            },
                            "styles": {
                                "background": "linear-gradient(45deg, #00f2fe 0%, #4facfe 100%)"
                            }
                        }
                    ]
                }
            ]
        }
        
        # Save to ui.json for verification
        with open("ui.json", "w") as f:
            json.dump(ui_data, f, indent=2)
            
        try:
            schema = validate_ui_json(ui_data)
            self.assertEqual(schema.name, "Arcturus Portfolio")
            self.assertEqual(len(schema.pages), 1)
            self.assertEqual(schema.pages[0].components[0].type, "hero")
            print("✅ ui.json validation passed!")
        except Exception as e:
            self.fail(f"Validation failed: {e}")
        finally:
            if os.path.exists("ui.json"):
                os.remove("ui.json")

if __name__ == "__main__":
    unittest.main()
