import networkx as nx
import json

def _extract_output(output):
    """
    Extract and properly serialize output from agent nodes.
    Handles nested dicts, lists, and strings properly.
    """
    if output is None:
        return ""
    
    if isinstance(output, str):
        return output
    
    if isinstance(output, dict):
        # Convert dict to JSON string for proper parsing on frontend
        return json.dumps(output)
    
    if isinstance(output, (list, tuple)):
        return json.dumps(output)
    
    # Fallback to string representation
    return str(output)

def nx_to_reactflow(graph: nx.DiGraph):
    """
    Convert a NetworkX graph to ReactFlow nodes and edges.
    """
    nodes = []
    edges = []

    # Calculate layout: Simple hierarchical (DAG) layout
    # Reset positions
    pos = {}
    
    # Simple Topological-like generation for Y-axis, spread for X-axis
    try:
        # Get generations/layers
        layers = list(nx.topological_generations(graph))
        
        # Calculate X,Y
        # X spacing: 300, Y spacing: 150
        for y_idx, layer in enumerate(layers):
            layer_width = len(layer) * 300
            start_x = -(layer_width / 2)
            
            for x_idx, node_id in enumerate(layer):
                pos[node_id] = {
                    "x": start_x + (x_idx * 300),
                    "y": y_idx * 200
                }
    except Exception:
        # Fallback to spring layout if not DAG or error
        spring_pos = nx.spring_layout(graph, scale=500, seed=42)
        for node_id, p in spring_pos.items():
            pos[node_id] = {"x": p[0]*500, "y": p[1]*500}

    # Simple formatting
    for node_id, data in graph.nodes(data=True):
        # Determine status color/variant mapping
        status = data.get("status", "pending")
        # Fix: correctly map 'agent' from JSON to 'agent_type' for UI
        agent_type = data.get("agent", data.get("agent_type", "Generic"))
        if node_id == "ROOT" or agent_type == "System":
            agent_type = "PlannerAgent"
        
        # Use calculated pos or default
        p = pos.get(node_id, {"x": 0, "y": 0})
        
        # Build node object
        nodes.append({
            "id": str(node_id),
            "type": "agentNode", # Matches AgentNode.tsx (case sensitive!)
            "position": p, 
            "data": {
                "label": agent_type or str(node_id),
                "type": agent_type,
                "status": status,
                "description": data.get("description", ""),
                "prompt": data.get("agent_prompt") or data.get("prompt") or data.get("description") or "",
                "reads": data.get("reads", []),
                "writes": data.get("writes", []),
                "cost": data.get("cost", 0.0),
                "execution_time": data.get("execution_time", 0.0),
                "output": _extract_output(data.get("output")),
                "error": str(data.get("error", "")) if data.get("error") else "",
                # Add missing fields required for Web Tab and Debugging
                "execution_result": data.get("execution_result"),
                "iterations": data.get("iterations", []),
                "logs": data.get("logs", []),
                "execution_logs": data.get("execution_logs", ""),
                "calls": data.get("calls", [])
            }
        })

    for u, v in graph.edges():
        edges.append({
            "id": f"e{u}-{v}",
            "source": str(u),
            "target": str(v),
            "type": "custom", # Matches CustomEdge.tsx
            "animated": False,  # Solid line, not dashed
            "style": { "stroke": "#888888", "strokeDasharray": "none" }  # Gray solid line
        })

    return {"nodes": nodes, "edges": edges}
