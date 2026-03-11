import json
import logging
from typing import List, Dict, Any, Optional
from playwright.async_api import Page
import time

logger = logging.getLogger("phantom-recorder")

class ActionRecorder:
    """
    Records user interactions on a page and generates workflow scripts.
    """
    
    def __init__(self, page: Page):
        self.page = page
        self.recorded_actions = []
        self.is_recording = False

    async def start_recording(self):
        """Inject recording script and start capturing events."""
        self.is_recording = True
        self.recorded_actions = []
        
        # Inject script to catch clicks and input, persistent across navigations
        self.recorder_js = """
            if (!window._phantom_recording_initialized) {
                window._phantom_events = window._phantom_events || [];
                window._phantom_recording = true;
                window._phantom_recording_initialized = true;
                
                const handleEvent = (e) => {
                    if (!window._phantom_recording) return;
                    
                    const element = e.target;
                    const selector = element.id ? `#${element.id}` : 
                                    element.name ? `[name="${element.name}"]` : 
                                    element.tagName.toLowerCase();
                    
                    const event = {
                        timestamp: Date.now(),
                        type: e.type,
                        selector: selector,
                        text: e.type === 'input' ? element.value : element.innerText
                    };
                    window._phantom_events.push(event);
                };
                
                document.addEventListener('click', handleEvent, true);
                document.addEventListener('input', handleEvent, true);
            }
        """
        await self.page.context.add_init_script(self.recorder_js)
        await self.page.evaluate(self.recorder_js)
        logger.info("Recording started (persistent across navigations)")

    async def stop_recording(self) -> Dict[str, Any]:
        """Stop recording and return the captured actions as a workflow."""
        self.is_recording = False
        # Collect events from all pages in context (simplified to current page for now)
        events = await self.page.evaluate("() => { window._phantom_recording = false; return window._phantom_events || []; }")
        
        # Convert events to workflow format
        steps = []
        for event in events:
            if event['type'] == 'click':
                steps.append({"action": "click", "selector": event['selector']})
            elif event['type'] == 'input':
                if steps and steps[-1]['action'] == 'type' and steps[-1]['selector'] == event['selector']:
                    steps[-1]['text'] = event['text']
                else:
                    steps.append({"action": "type", "selector": event['selector'], "text": event['text']})
        
        workflow = {
            "name": f"Recorded Workflow {int(time.time())}",
            "steps": steps
        }
        
        logger.info(f"Recording stopped. Captured {len(steps)} steps.")
        return workflow

    async def get_recorded_actions(self) -> List[Dict[str, Any]]:
        """Retrieve current buffer of recorded actions."""
        return await self.page.evaluate("() => window._phantom_events || []")
