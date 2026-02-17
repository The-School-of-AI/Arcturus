import requests
import sys

BASE_URL = "http://localhost:8000"

def test_inbox():
    print("Testing Inbox API...")
    
    # 1. Create Notification
    payload = {
        "source": "CLI_Test",
        "title": "Hello from CLI",
        "body": "This is a **markdown** test message.",
        "priority": 2
    }
    
    # Note: This requires the server to be running. 
    # Since we can't easily assert on a running server in this strict environment without background processes,
    # This script is designed to be run by the user or a separate process.
    # However, for this environment, I will simulate the DB interaction directly to verify the logic works 
    # if the server isn't up, OR I will assume the server is up for the "interactive" part.
    
    # But wait, I can just import the module and test the function directly!
    # That's much better for a self-contained test.
    
    sys.path.append(".")
    from routers.inbox import send_to_inbox, get_notifications, mark_as_read, delete_notification, init_db
    
    print("✅ Module imported.")
    init_db()
    
    print("1. Sending notification...")
    notif_id = send_to_inbox("CLI_Test", "Direct Test", "Direct Body", 2)
    print(f"   Created ID: {notif_id}")
    
    print("2. Reading notifications...")
    # asyncio run for async endpoints if I were calling them, but send_to_inbox is sync.
    # The endpoints are async, but the logic inside interacts with DB synchronously (sqlite3 dict cursor).
    # Wait, the endpoints in routers/inbox.py are async def, but they call synchronous sqlite3.
    # That's technically blocking the event loop but fine for sqlite usually.
    
    # Let's verify the DB content directly.
    import sqlite3
    conn = sqlite3.connect("data/inbox/notifications.db")
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM notifications WHERE id=?", (notif_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        print(f"✅ Found in DB: {row[2]} - {row[3]}")
    else:
        print("❌ Not found in DB!")
        sys.exit(1)
        
    print("Inbox Test Passed!")

if __name__ == "__main__":
    test_inbox()
