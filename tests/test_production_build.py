
import asyncio
import unittest
import sys
import os
import shutil
import subprocess
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

from core.schemas.ui_schema import AppSchema, Style, Page, Component
from core.ui_generator import ViteAppGenerator

class TestProductionBundle(unittest.IsolatedAsyncioTestCase):
    async def test_build_and_assets(self):
        output_dir = "production_app"
        generator = ViteAppGenerator(output_dir=output_dir)
        
        config = AppSchema(
            name="Production Test App",
            theme=Style(),
            pages=[
                Page(
                    title="Home",
                    path="/",
                    components=[
                        Component(id="h1", type="hero", title="Built with Arcturus", content={"subtitle": "Production Grade"})
                    ]
                )
            ]
        )
        
        # 1. Generate project
        generator.generate_project_structure(config)
        
        # 2. Add hero image (converted to WebP)
        # Find the image generated in previous step
        # For simplicity in test, we'll look for any .png in the task directory
        # but here we'll just mock a small png for the build test if not found.
        
        public_dir = Path(output_dir) / "public"
        hero_webp = public_dir / "hero.webp"
        
        # We'll use the image from the previous generate_image call if possible
        # but for a self-contained test, let's just create a dummy file if needed.
        # Actually, let's use ffmpeg if we have an image.
        
        image_path = "/Users/rohanshravan/.gemini/antigravity/brain/e3740c39-2f86-4cfe-bdfa-8a2252eb5d83/hero_vibrant_abstract_1771229932023.png"
        
        if os.path.exists(image_path):
            print(f"🖼️  Converting {image_path} to WebP...")
            subprocess.run(["ffmpeg", "-i", image_path, "-y", str(hero_webp)], check=True)
        else:
            print("⚠️  Image not found, creating dummy webp for build test.")
            hero_webp.write_text("fake-webp-content")
            
        # 3. Build (This takes time, we'll skip npm install if node_modules exists elsewhere
        # or we just do it once)
        try:
            generator.build_app()
            
            # 4. Verify dist
            dist_dir = Path(output_dir) / "dist"
            self.assertTrue(dist_dir.exists())
            
            # Check if assets are there
            assets_dir = dist_dir / "assets"
            # In Vite, index.html is at root of dist
            self.assertTrue((dist_dir / "index.html").exists())
            
            # Check if our webp was copied to dist (public assets go to dist root)
            self.assertTrue((dist_dir / "hero.webp").exists())
            
            print("✅ Production bundle verification passed!")
        except Exception as e:
            self.fail(f"Build failed: {e}")
        # finally:
        #     if os.path.exists(output_dir):
        #         shutil.rmtree(output_dir)

if __name__ == "__main__":
    asyncio.run(unittest.main())
