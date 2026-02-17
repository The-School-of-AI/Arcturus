
import unittest
import sys
import os
import shutil
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.schemas.ui_schema import AppSchema, Style, Page, Component
from core.ui_generator import ViteAppGenerator

class TestUIGenerator(unittest.TestCase):
    def test_project_generation(self):
        output_dir = "test_generated_site"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            
        generator = ViteAppGenerator(output_dir=output_dir)
        
        config = AppSchema(
            name="Test App",
            theme=Style(colors={"primary": "#ff0000", "secondary": "#00ff00", "background": "#000000", "text": "#ffffff"}),
            pages=[
                Page(
                    title="Home",
                    path="/",
                    components=[
                        Component(id="h1", type="hero", title="Welcome", content={"subtitle": "Hello world", "cta": "Click Me"})
                    ]
                )
            ]
        )
        
        generator.generate_project_structure(config)
        
        # Verify files
        self.assertTrue(os.path.exists(f"{output_dir}/index.html"))
        self.assertTrue(os.path.exists(f"{output_dir}/src/App.jsx"))
        self.assertTrue(os.path.exists(f"{output_dir}/src/index.css"))
        
        # Verify content briefly
        app_content = Path(f"{output_dir}/src/App.jsx").read_text()
        css_content = Path(f"{output_dir}/src/index.css").read_text()
        self.assertIn("Welcome", app_content)
        self.assertIn("#000000", css_content)
        
        print("✅ Vite app generator project structure passed!")
        
        # Cleanup
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)

if __name__ == "__main__":
    unittest.main()
