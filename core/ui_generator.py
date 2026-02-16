
import os
import shutil
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List
from core.schemas.ui_schema import AppSchema, Component

class ViteAppGenerator:
    """Generates a React/Vite project from an AppSchema."""
    
    def __init__(self, output_dir: str = "generated_app"):
        self.output_dir = Path(output_dir)
        # Clean start
        if self.output_dir.exists():
            shutil.rmtree(self.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate_project_structure(self, app_config: AppSchema):
        self.generate_package_json(app_config.name)
        self.generate_vite_config()
        self.generate_index_html(app_config.name)
        self.generate_src(app_config)
        
        # public dir
        (self.output_dir / "public").mkdir(exist_ok=True)

    def generate_package_json(self, name: str):
        content = {
            "name": name.lower().replace(" ", "-"),
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
            },
            "dependencies": {
                "react": "^18.3.1",
                "react-dom": "^18.3.1"
            },
            "devDependencies": {
                "@vitejs/plugin-react": "^4.3.2",
                "vite": "^5.4.8"
            }
        }
        (self.output_dir / "package.json").write_text(json.dumps(content, indent=2))

    def generate_vite_config(self):
        content = """
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
})
"""
        (self.output_dir / "vite.config.js").write_text(content)

    def generate_index_html(self, title: str):
        content = f"""
<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
"""
        (self.output_dir / "index.html").write_text(content)

    def generate_src(self, app_config: AppSchema):
        src_dir = self.output_dir / "src"
        src_dir.mkdir(exist_ok=True)
        
        # main.jsx
        (src_dir / "main.jsx").write_text("""
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
""")
        
        # index.css
        theme = app_config.theme
        (src_dir / "index.css").write_text(f"""
body {{
  margin: 0;
  font-family: Inter, system-ui, sans-serif;
  background: {theme.colors.get('background', '#0f172a')};
  color: {theme.colors.get('text', '#f8fafc')};
}}
.container {{ max-width: 1200px; margin: 0 auto; padding: 0 20px; }}
.hero {{ padding: 100px 0; text-align: center; }}
.hero h1 {{ font-size: 4rem; margin-bottom: 1rem; }}
""")

        # App.jsx
        components_jsx = []
        for page in app_config.pages:
            for comp in page.components:
                if comp.type == "hero":
                    components_jsx.append(f"""
        <section className="hero">
          <div className="container">
            <h1>{comp.title or "Untitled"}</h1>
            <p>{comp.content.get('subtitle', '') if isinstance(comp.content, dict) else ''}</p>
            <img src="/hero.webp" alt="Hero" style={{{{ maxWidth: '100%', borderRadius: '16px' }}}} />
          </div>
        </section>
""")

        app_jsx = f"""
import React from 'react'

function App() {{
  return (
    <div className="app">
      {''.join(components_jsx)}
    </div>
  )
}}

export default App
"""
        (src_dir / "App.jsx").write_text(app_jsx)

    def build_app(self):
        """Run npm install and npm run build."""
        print("📦 Installing dependencies (this might take a minute)...")
        # Skipping npm install in unit tests to save time, but for verification we need it.
        # We'll use --prefer-offline to speed it up
        subprocess.run(["npm", "install", "--prefer-offline"], cwd=self.output_dir, check=True)
        print("🏗️  Building production bundle...")
        subprocess.run(["npm", "run", "build"], cwd=self.output_dir, check=True)
        print("✅ Build complete!")
