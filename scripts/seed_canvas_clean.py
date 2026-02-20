import json
from pathlib import Path

def seed_clean():
    path = Path("storage/canvas/main-canvas.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    
    data = {
        "components": [
            {
                "id": "root",
                "component": "Container",
                "props": {"className": "p-6 space-y-4"},
                "children": ["title", "chart"]
            },
            {
                "id": "title",
                "component": "Text",
                "props": {"content": "System Verification Report", "style": {"fontSize": "24px", "fontWeight": "bold"}}
            },
            {
                "id": "chart",
                "component": "LineChart",
                "props": {
                    "title": "Agent Performance Over Time",
                    "xKey": "time",
                    "lines": [{"key": "score", "color": "#10B981"}],
                    "data": [
                        {"time": "10:00", "score": 85},
                        {"time": "10:05", "score": 88},
                        {"time": "10:10", "score": 92}
                    ]
                }
            }
        ],
        "data": {}
    }
    
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"✅ Clean state written to {path}")

if __name__ == "__main__":
    seed_clean()
