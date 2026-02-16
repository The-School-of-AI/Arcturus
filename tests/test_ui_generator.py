
import unittest
import sys
import os
import shutil
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.schemas.ui_schema import AppSchema, Style, Page, Component
from core.ui_generator import DynamicPageGenerator

class TestUIGenerator(unittest.TestCase):
    def test_full_app_generation(self):
        output_dir = "test_generated_site"
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)
            
        generator = DynamicPageGenerator(output_dir=output_dir)
        
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
                ),
                Page(
                    title="About",
                    path="/about",
                    components=[
                        Component(id="h2", type="hero", title="About Us")
                    ]
                )
            ]
        )
        
        generator.generate_app(config)
        
        # Verify files
        self.assertTrue(os.path.exists(f"{output_dir}/index.html"))
        self.assertTrue(os.path.exists(f"{output_dir}/about.html"))
        
        # Verify content briefly
        index_content = Path(f"{output_dir}/index.html").read_text()
        self.assertIn("Welcome", index_content)
        self.assertIn("#ff0000", index_content) # Primary color should be there
        
        print("✅ Dynamic Page Generator (multi-page) passed!")
        
        # Cleanup
        if os.path.exists(output_dir):
            shutil.rmtree(output_dir)

if __name__ == "__main__":
    unittest.main()
