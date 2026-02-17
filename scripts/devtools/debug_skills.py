
import requests
import json

def list_remote_skills():
    url = "https://api.github.com/repos/sickn33/antigravity-awesome-skills/contents/skills"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        print("--- Remote Skills ---")
        for item in data:
            if item['type'] == 'dir':
                print(item['name'])
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    list_remote_skills()
