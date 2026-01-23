import asyncio
import json
import logging
import sys
# Imports removed


# Pre-requisite: pip install httpx httpx-sse
# If not installed, this script will fail. I will assume user/environment might need it.
# But for now I'll use standard library or just basic curl simulation concept if httpx is hard.
# Actually, I can use the `core.event_bus` directly since I'm in the same process/environment for a test script 
# (simulating backend consuming itself, or just unit test style).

# But the plan said "CLI Test: Listener script to print events".
# Ideally it connects to localhost:8000/events.
# Since I can't guarantee server is running in this env, I will test the core `event_bus` logic directly.

sys.path.append(".")
from core.event_bus import event_bus

async def test_event_bus():
    print("Testing Event Bus Core...")
    
    # 1. Subscribe
    queue = await event_bus.subscribe()
    print("✅ Subscribed.")
    
    # 2. Publish Event
    print("📢 Publishing 'test_event'...")
    await event_bus.publish("test_event", "CLI_Test", {"message": "Hello World"})
    
    # 3. Receive Event
    print("👂 Waiting for event...")
    event = await queue.get()
    print(f"✅ Received: {event['type']} from {event['source']}")
    print(f"   Data: {event['data']}")
    
    event_bus.unsubscribe(queue)
    print("🎉 Event Bus Test Complete.")

if __name__ == "__main__":
    asyncio.run(test_event_bus())
