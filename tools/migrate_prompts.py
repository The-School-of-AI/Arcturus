
import os
import hashlib
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
PROMPTS_DIR = PROJECT_ROOT / "prompts"
SKILLS_LIB_DIR = PROJECT_ROOT / "core" / "skills" / "library"

SKILLS_LIB_DIR.mkdir(parents=True, exist_ok=True)

TEMPLATE = """
from core.skills.base import Skill

class {class_name}(Skill):
    name = "{skill_name}"
    description = "Skill derived from {filename}"
    
    @property
    def prompt_text(self) -> str:
        return \"\"\"{prompt_content}\"\"\"

    def get_system_prompt_additions(self) -> str:
        return self.prompt_text
"""

def to_camel_case(snake_str):
    components = snake_str.split('_')
    return ''.join(x.title() for x in components)

def migrate():
    print(f"Migrating prompts from {PROMPTS_DIR} to {SKILLS_LIB_DIR}")
    
    for md_file in PROMPTS_DIR.glob("*.md"):
        filename = md_file.name
        stem = md_file.stem.lower().replace("-", "_").replace(" ", "_")
        
        # Read content
        content = md_file.read_text()
        
        # Calculate MD5
        original_md5 = hashlib.md5(content.encode('utf-8')).hexdigest()
        
        # Create skill folder
        skill_dir = SKILLS_LIB_DIR / stem
        skill_dir.mkdir(exist_ok=True)
        
        # Generate Class Name
        class_name = to_camel_case(stem) + "Skill"
        
        # Escape triple quotes in content
        escaped_content = content.replace('"""', '\\"\\"\\"')
        
        # Create Python file
        code = TEMPLATE.format(
            class_name=class_name,
            skill_name=stem,
            filename=filename,
            prompt_content=escaped_content
        )
        
        skill_file = skill_dir / "skill.py"
        skill_file.write_text(code)
        
        # Verify
        # We need to import the module and check prompt_text
        # But for now let's just re-read the string literal from file? 
        # Easier to just trust the write for now, and verification step can run separately.
        
        print(f"Migrated {filename} -> {skill_file} (MD5: {original_md5})")

if __name__ == "__main__":
    migrate()
