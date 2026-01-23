import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from core.skills.manager import skill_manager

print("Initializing Skill Manager...")
skill_manager.initialize()

print("\n--- Registry Content ---")
print(skill_manager.registry_file.read_text())

print("\n--- Intent Matching Test ---")
test_queries = [
    "Check apple stock price",
    "Give me tonight's news briefing",
    "Make me a sandwich"
]

for q in test_queries:
    match = skill_manager.match_intent(q)
    print(f"Query: '{q}' -> Skill: {match}")
