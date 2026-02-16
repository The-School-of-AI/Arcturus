
import yaml
from pathlib import Path
from core.registry import AgentRegistry
from core.utils import log_step

def bootstrap_agents():
    """
    Load agent configurations from agent_config.yaml and register them 
    into the AgentRegistry.
    This replaces the hardcoded loading in AgentRunner.
    """
    config_path = Path(__file__).parent.parent / "config/agent_config.yaml"
    
    if not config_path.exists():
        log_step(f"⚠️ Agent config not found at {config_path}", symbol="⚠️")
        return

    try:
        with open(config_path, "r") as f:
            config_data = yaml.safe_load(f)
            
        agents = config_data.get("agents", {})
        count = 0
        for name, agent_config in agents.items():
            # In the future, we might have different classes for different agents.
            # For now, they are all generic configurations run by AgentRunner.
            # We register the CONFIG DICTIONARY itself.
            desc = agent_config.get("description", "Loaded from yaml")
            AgentRegistry.register(name, agent_config, description=desc)
            count += 1
            
        log_step(f"✅ Bootstrapped {count} agents into Registry", symbol="🚀")
        
    except Exception as e:
        log_step(f"❌ Failed to bootstrap agents: {e}", symbol="❌")
        raise
