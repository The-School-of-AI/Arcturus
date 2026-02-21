from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

router = APIRouter(
    prefix="/counter-pro",
    tags=["Counter Pro Dashboard"],
    responses={404: {"description": "Not found"}},
)

# --- Pydantic Models for the Dashboard Spec ---

# Generic data model to accommodate various card data structures
class CardData(BaseModel):
    value: Optional[Any] = None
    change: Optional[float] = None
    trend: Optional[str] = None
    text: Optional[str] = None
    series: Optional[List[Dict[str, Any]]] = None
    points: Optional[List[Dict[str, Any]]] = None
    headers: Optional[List[str]] = None
    rows: Optional[List[List[Any]]] = None
    items: Optional[List[Dict[str, Any]]] = None
    label: Optional[str] = None
    options: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    min: Optional[int] = None
    max: Optional[int] = None
    content: Optional[str] = None
    title: Optional[str] = None
    xLabel: Optional[str] = None
    yLabel: Optional[str] = None
    slices: Optional[List[Dict[str, Any]]] = None

class Card(BaseModel):
    id: str
    type: str
    label: str
    context: str
    config: Dict[str, Any]
    data: CardData
    style: Dict[str, Any]

class LayoutItem(BaseModel):
    i: str
    x: int
    y: int
    w: int
    h: int

class DashboardSpec(BaseModel):
    id: str
    name: str
    description: str
    cards: List[Card]
    layout: List[LayoutItem]
    lastModified: int

# --- In-memory State for Dynamic Dashboard Data ---

# Initial values for resetting and starting point
INITIAL_TOTAL_EVENTS = 1000
INITIAL_UNIQUE_USERS = 500
INITIAL_AVG_EVENTS_HOUR = 50
INITIAL_ERROR_RATE = 0.5 # percentage

# This dictionary holds the dynamic data that changes with user interaction or time
# It's initialized and reset by functions below.
dashboard_state: Dict[str, Any] = {}

# The original static parts of the spec. Dynamic data from 'dashboard_state' will be
# merged into this when generating the full spec response.
ORIGINAL_SPEC_STATIC_PARTS = {
    "id": "app-1771690736897",
    "name": "Counter Pro",
    "description": "A simple counter app with a reset button.",
    "cards": [
        {"id": "dashboard-header", "type": "header", "label": "Event Tracking Dashboard", "context": "Main title for the event tracking dashboard.", "config": {"centered": True, "bold": True}, "data": {"text": "Event Tracking Dashboard"}, "style": {}},
        # Dynamic cards will have their 'data' field updated from dashboard_state
        {"id": "total-events-today", "type": "metric", "label": "Total Events Today", "context": "The total number of events recorded in the current day.", "config": {}, "data": {}, "style": {}},
        {"id": "unique-users", "type": "trend", "label": "Unique Users Today", "context": "The number of unique users who triggered events today, with a sparkline trend.", "config": {"showSparkline": True}, "data": {}, "style": {}},
        {"id": "avg-events-hour", "type": "metric", "label": "Avg. Events/Hour", "context": "The average number of events per hour over the last 24 hours.", "config": {}, "data": {}, "style": {}},
        {"id": "error-rate", "type": "trend", "label": "Error Rate", "context": "The percentage of events that resulted in an error, with a sparkline trend.", "config": {"showSparkline": True}, "data": {}, "style": {}},
        {"id": "hourly-event-volume-chart", "type": "line_chart", "label": "Hourly Event Volume Trend", "context": "Trend of total event volume over the last 24 hours, categorized by event type.", "config": {}, "data": {"title": "Hourly Event Volume (Last 24h)", "xLabel": "Hour", "yLabel": "Event Count", "series": []}, "style": {}},
        # Static cards (their data field is fully defined here)
        {"id": "events-by-type-chart", "type": "bar_chart", "label": "Events by Type (Today)", "context": "Distribution of events grouped by their category or type for the current day.", "config": {}, "data": {"title": "Events by Type (Today)", "xLabel": "Event Type", "yLabel": "Count", "points": [{"x": "Click", "y": 4500, "color": "#F5C542"}, {"x": "Page View", "y": 3200, "color": "#4ecdc4"}, {"x": "Form Submit", "y": 1800, "color": "#ff6b6b"}, {"x": "Error", "y": 700, "color": "#a29bfe"}, {"x": "API Call", "y": 2600, "color": "#00cec9"}]}, "style": {}},
        {"id": "timeframe-selector", "type": "select", "label": "Select Timeframe", "context": "Dropdown to choose the data aggregation period for the dashboard.", "config": {}, "data": {"label": "Timeframe", "options": ["Last Hour", "Today", "Last 7 Days", "Last 30 Days"], "value": "Today"}, "style": {}},
        {"id": "filter-by-tag-input", "type": "tags_input", "label": "Filter by Event Tag", "context": "Input field to filter events by specific tags or keywords.", "config": {}, "data": {"tags": ["user-action", "critical"]}, "style": {}},
        {"id": "threshold-alert-input", "type": "number_input", "label": "Set Alert Threshold", "context": "Input to set a numerical threshold for an alert system.", "config": {}, "data": {"label": "Max Errors/Hour", "min": 0, "max": 1000, "value": 50}, "style": {}},
        {"id": "reset-counters-button", "type": "button", "label": "Reset Daily Counters", "context": "Button to reset all daily event counters and start a new tracking period.", "config": {}, "data": {"label": "Reset Daily Counters"}, "style": {}},
        {"id": "recent-event-log", "type": "table", "label": "Recent Event Log", "context": "A table displaying the most recent events with their details.", "config": {}, "data": {"headers": ["Timestamp", "Event Type", "User ID", "Status"], "rows": [["2024-07-20 14:35:01", "Page View", "UID-001", "Success"], ["2024-07-20 14:34:58", "Button Click", "UID-002", "Success"], ["2024-07-20 14:34:55", "API Error", "UID-003", "Failed"], ["2024-07-20 14:34:50", "Form Submit", "UID-001", "Success"], ["2024-07-20 14:34:42", "Login Attempt", "UID-004", "Success"], ["2024-07-20 14:34:30", "DB Query", "UID-005", "Success"]]}, "style": {}},
        {"id": "system-notifications-feed", "type": "feed", "label": "System Notifications", "context": "A feed displaying important system notifications or alerts related to event tracking.", "config": {}, "data": {"items": [{"title": "High error rate detected", "time": "5m ago", "description": "Error rate spiked to 3.5%"}, {"title": "Daily report generated", "time": "30m ago", "description": "Event summary for July 19th available."}, {"title": "New event type added", "time": "2h ago", "description": "Tracking for 'Video Playback' initiated."}, {"title": "Database connection stable", "time": "4h ago", "description": "All event logs are being recorded."}, {"title": "Low event volume", "time": "8h ago", "description": "Consider checking system health."}]}, "style": {}},
        {"id": "performance-highlights", "type": "stats_trending", "label": "Performance Highlights", "context": "Key performance indicators with their trending values for events.", "config": {}, "data": {"items": [{"label": "Conversion Rate", "value": "4.5%", "change": "+0.3%"}, {"label": "Page Load Time", "value": "1.2s", "change": "-0.1s"}, {"label": "Active Sessions", "value": "1,520", "change": "+120"}]}, "style": {}},
        {"id": "device-type-distribution", "type": "pie_chart", "label": "Device Type Distribution", "context": "Distribution of events based on the device type (desktop, mobile, tablet).", "config": {}, "data": {"title": "Events by Device Type", "slices": [{"name": "Desktop", "value": 55, "color": "#F5C542"}, {"name": "Mobile", "value": 40, "color": "#4ecdc4"}, {"name": "Tablet", "value": 5, "color": "#a29bfe"}]}, "style": {}},
        {"id": "service-health-status", "type": "stats_status", "label": "Service Health Status", "context": "Status of various underlying services contributing to event tracking.", "config": {}, "data": {"items": [{"name": "Event Collector", "status": "online"}, {"name": "Database Sync", "status": "online"}, {"name": "API Gateway", "status": "online"}, {"name": "Analytics Engine", "status": "online"}]}, "style": {}},
        {"id": "dashboard-insights", "type": "markdown", "label": "Dashboard Insights", "context": "A markdown block providing textual insights and analysis of the displayed event data.", "config": {}, "data": {"content": "## Event Performance Summary\nThis dashboard provides a real-time view of event activities. Key observations:\n*   **User interaction** is currently peaking during business hours.\n*   A slight **increase in error rate** requires further investigation.\n*   Mobile event volume remains strong, indicating a healthy mobile user base."}, "style": {}}
    ],
    "layout": [{"i": "dashboard-header", "x": 0, "y": 0, "w": 24, "h": 2}, {"i": "total-events-today", "x": 0, "y": 2, "w": 6, "h": 3}, {"i": "unique-users", "x": 6, "y": 2, "w": 6, "h": 3}, {"i": "avg-events-hour", "x": 12, "y": 2, "w": 6, "h": 3}, {"i": "error-rate", "x": 18, "y": 2, "w": 6, "h": 3}, {"i": "hourly-event-volume-chart", "x": 0, "y": 5, "w": 12, "h": 8}, {"i": "events-by-type-chart", "x": 12, "y": 5, "w": 12, "h": 8}, {"i": "timeframe-selector", "x": 0, "y": 13, "w": 6, "h": 2}, {"i": "filter-by-tag-input", "x": 6, "y": 13, "w": 8, "h": 2}, {"i": "threshold-alert-input", "x": 14, "y": 13, "w": 6, "h": 2}, {"i": "reset-counters-button", "x": 20, "y": 13, "w": 4, "h": 2}, {"i": "recent-event-log", "x": 0, "y": 15, "w": 12, "h": 8}, {"i": "system-notifications-feed", "x": 12, "y": 15, "w": 12, "h": 8}, {"i": "performance-highlights", "x": 0, "y": 23, "w": 12, "h": 6}, {"i": "device-type-distribution", "x": 12, "y": 23, "w": 12, "h": 6}, {"i": "service-health-status", "x": 0, "y": 29, "w": 12, "h": 5}, {"i": "dashboard-insights", "x": 12, "y": 29, "w": 12, "h": 5}],
    "lastModified": 1771690759704
}


def _initialize_dashboard_state():
    """Initializes or resets the dynamic parts of the dashboard state."""
    global dashboard_state
    dashboard_state["total-events-today"] = {
        "value": INITIAL_TOTAL_EVENTS,
        "change": 0.0,
        "trend": "neutral"
    }
    dashboard_state["unique-users"] = {
        "value": INITIAL_UNIQUE_USERS,
        "change": 0.0
    }
    dashboard_state["avg-events-hour"] = {
        "value": INITIAL_AVG_EVENTS_HOUR,
        "change": 0.0,
        "trend": "neutral"
    }
    dashboard_state["error-rate"] = {
        "value": INITIAL_ERROR_RATE,
        "change": 0.0
    }
    # Initialize hourly chart with some baseline data
    dashboard_state["hourly-event-volume-chart"] = {
        "series": [
            {"name": "User Interactions", "color": "#4ecdc4", "data": [{"x": f"{i:02d}:00", "y": INITIAL_TOTAL_EVENTS // 8} for i in range(0, 24, 3)]},
            {"name": "System Events", "color": "#ff6b6b", "data": [{"x": f"{i:02d}:00", "y": INITIAL_TOTAL_EVENTS // 20} for i in range(0, 24, 3)]}
        ]
    }

# Initialize the state when the router is loaded
_initialize_dashboard_state()


def _get_current_dashboard_spec() -> DashboardSpec:
    """
    Constructs the complete DashboardSpec by merging static parts with current dynamic state.
    """
    current_cards = []
    for card_spec in ORIGINAL_SPEC_STATIC_PARTS["cards"]:
        card_id = card_spec["id"]
        card_data = card_spec["data"].copy() # Start with static data if any

        # Override or add data from the dynamic state
        if card_id == "total-events-today":
            state = dashboard_state[card_id]
            card_data["value"] = f"{state['value']:,}"
            card_data["change"] = state['change']
            card_data["trend"] = state['trend']
        elif card_id == "unique-users":
            state = dashboard_state[card_id]
            card_data["value"] = f"{state['value']:,}"
            card_data["change"] = state['change']
        elif card_id == "avg-events-hour":
            state = dashboard_state[card_id]
            card_data["value"] = f"{state['value']:,}"
            card_data["change"] = state['change']
            card_data["trend"] = state['trend']
        elif card_id == "error-rate":
            state = dashboard_state[card_id]
            card_data["value"] = f"{state['value']:.1f}%"
            card_data["change"] = state['change']
        elif card_id == "hourly-event-volume-chart":
            card_data["series"] = dashboard_state[card_id]["series"]

        current_cards.append(Card(id=card_id, type=card_spec["type"], label=card_spec["label"],
                                  context=card_spec["context"], config=card_spec["config"],
                                  data=card_data, style=card_spec["style"]))

    return DashboardSpec(
        id=ORIGINAL_SPEC_STATIC_PARTS["id"],
        name=ORIGINAL_SPEC_STATIC_PARTS["name"],
        description=ORIGINAL_SPEC_STATIC_PARTS["description"],
        cards=current_cards,
        layout=[LayoutItem(**item) for item in ORIGINAL_SPEC_STATIC_PARTS["layout"]],
        lastModified=ORIGINAL_SPEC_STATIC_PARTS["lastModified"] # In a real app, this might update
    )

# --- FastAPI Endpoints ---

@router.get("/", response_model=DashboardSpec, summary="Get entire dashboard specification and current data")
async def get_dashboard_spec():
    """
    Returns the complete dashboard specification, including dynamic data for metrics.
    This endpoint serves the entire layout and component data for the frontend.
    """
    return _get_current_dashboard_spec()


@router.get("/data/{card_id}", response_model=CardData, summary="Get data for a specific card")
async def get_card_data(card_id: str):
    """
    Returns the data for a specific card by its ID.
    Dynamic cards will reflect the current state.
    """
    current_spec = _get_current_dashboard_spec()
    for card in current_spec.cards:
        if card.id == card_id:
            return card.data
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Card with ID '{card_id}' not found.")


@router.post("/events/increment", response_model=DashboardSpec, summary="Increment Total Events Today counter")
async def increment_event_counter(amount: int = 1):
    """
    Increments the 'Total Events Today' counter by the specified `amount` (defaults to 1).
    Also simulates updates to related metrics like Unique Users and Avg. Events/Hour.
    Returns the updated dashboard specification.
    """
    global dashboard_state
    
    # Update Total Events Today
    old_total_events = dashboard_state["total-events-today"]["value"]
    new_total_events = old_total_events + amount
    
    change_percentage = ((new_total_events - INITIAL_TOTAL_EVENTS) / INITIAL_TOTAL_EVENTS) * 100 if INITIAL_TOTAL_EVENTS else 0
    
    dashboard_state["total-events-today"]["value"] = new_total_events
    dashboard_state["total-events-today"]["change"] = round(change_percentage, 1)
    dashboard_state["total-events-today"]["trend"] = "up" if change_percentage > 0 else "neutral" if change_percentage == 0 else "down"

    # Simulate Unique Users increasing (e.g., a fraction of new events come from new users)
    dashboard_state["unique-users"]["value"] += amount // 5 
    dashboard_state["unique-users"]["change"] = round(((dashboard_state["unique-users"]["value"] - INITIAL_UNIQUE_USERS) / INITIAL_UNIQUE_USERS) * 100, 1) if INITIAL_UNIQUE_USERS else 0

    # Simulate Avg. Events/Hour
    dashboard_state["avg-events-hour"]["value"] = new_total_events // 24
    dashboard_state["avg-events-hour"]["change"] = round(((dashboard_state["avg-events-hour"]["value"] - INITIAL_AVG_EVENTS_HOUR) / INITIAL_AVG_EVENTS_HOUR) * 100, 1) if INITIAL_AVG_EVENTS_HOUR else 0
    dashboard_state["avg-events-hour"]["trend"] = "up" if dashboard_state["avg-events-hour"]["change"] > 0 else "neutral"

    # Simulate Error Rate (slight fluctuation)
    dashboard_state["error-rate"]["value"] = round(max(0.1, INITIAL_ERROR_RATE + (amount * 0.00001)), 1)
    dashboard_state["error-rate"]["change"] = round(dashboard_state["error-rate"]["value"] - INITIAL_ERROR_RATE, 1)

    # Update hourly chart data (simple increment to the latest hour point)
    if dashboard_state["hourly-event-volume-chart"]["series"][0]["data"]:
        dashboard_state["hourly-event-volume-chart"]["series"][0]["data"][-1]["y"] += amount
    if dashboard_state["hourly-event-volume-chart"]["series"][1]["data"]:
        dashboard_state["hourly-event-volume-chart"]["series"][1]["data"][-1]["y"] += amount // 2

    return _get_current_dashboard_spec()


@router.post("/actions/reset-daily-counters", response_model=DashboardSpec, summary="Reset all daily event counters")
async def reset_daily_counters():
    """
    Resets all daily event counters and related metrics to their initial state.
    This action corresponds to the 'Reset Daily Counters' button in the dashboard spec.
    Returns the updated dashboard specification after reset.
    """
    _initialize_dashboard_state()
    return _get_current_dashboard_spec()

# --- Placeholder Endpoints for Other Interactive Components ---

class TimeframeUpdate(BaseModel):
    value: str

@router.post("/actions/update-timeframe", summary="Update the dashboard's data timeframe")
async def update_timeframe(selection: TimeframeUpdate):
    """
    Placeholder endpoint for updating the dashboard's data aggregation timeframe.
    In a real application, this would trigger data re-fetching or re-aggregation.
    """
    # For now, just log and return a success message
    print(f"Timeframe updated to: {selection.value}")
    return {"message": f"Timeframe set to {selection.value}", "current_timeframe": selection.value}

class TagsUpdate(BaseModel):
    tags: List[str]

@router.post("/actions/filter-by-tags", summary="Filter events by specific tags")
async def filter_by_tags(tags_input: TagsUpdate):
    """
    Placeholder endpoint for filtering dashboard events by specific tags.
    In a real application, this would modify data queries for relevant cards.
    """
    print(f"Filtering by tags: {tags_input.tags}")
    return {"message": f"Filters applied: {tags_input.tags}", "current_tags": tags_input.tags}

class ThresholdUpdate(BaseModel):
    value: int

@router.post("/actions/set-alert-threshold", summary="Set a numerical alert threshold")
async def set_alert_threshold(threshold_input: ThresholdUpdate):
    """
    Placeholder endpoint for setting a numerical alert threshold.
    In a real application, this would configure an alert monitoring system.
    """
    print(f"Alert threshold set to: {threshold_input.value}")
    return {"message": f"Alert threshold set to {threshold_input.value}", "current_threshold": threshold_input.value}