from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse
from core.event_bus import event_bus
import asyncio
import json

router = APIRouter(tags=["Stream"])

@router.get("/events")
async def event_stream(request: Request):
    """
    Server-Sent Events (SSE) endpoint.
    Clients connect here to receive real-time updates from the system.
    """
    queue = await event_bus.subscribe()
    
    async def event_generator():
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break
                
                # Get event from queue
                event = await queue.get()
                yield {
                    "event": "message",
                    "data": json.dumps(event)
                }
        except asyncio.CancelledError:
            pass
        finally:
            event_bus.unsubscribe(queue)

    return EventSourceResponse(event_generator())
