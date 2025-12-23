import networkx as nx

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
                "prompt": data.get("agent_prompt", ""),
                "reads": data.get("reads", []),
                "writes": data.get("writes", []),
                "cost": data.get("cost", 0.0),
                "execution_time": data.get("execution_time", 0.0),
                "output": str(data.get("output", "")) if data.get("output") else "",
                "error": str(data.get("error", "")) if data.get("error") else ""
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
