import yaml
import json
from pathlib import Path
from typing import Optional
from core.model_manager import ModelManager
from core.json_parser import parse_llm_json
from core.utils import log_step, log_error
from PIL import Image
from datetime import datetime
import os

class AgentRunner:
    def __init__(self, multi_mcp):
        self.multi_mcp = multi_mcp
        
        # Load agent configurations
        config_path = Path(__file__).parent.parent / "config/agent_config.yaml"
        with open(config_path, "r") as f:
            self.agent_configs = yaml.safe_load(f)["agents"]
    
    def calculate_cost(self, input_text: str, output_text: str) -> dict:
        """Calculate cost and token usage"""
        # Approximate tokens = words * 1.5
        input_words = len(input_text.split()) if input_text else 0
        output_words = len(output_text.split()) if output_text else 0
        
        input_tokens = int(input_words * 1.5)
        output_tokens = int(output_words * 1.5)
        
        # Cost per million tokens
        input_cost_per_million = 0.1  # $0.1 per 1M input tokens
        output_cost_per_million = 0.4  # $0.4 per 1M output tokens
        
        input_cost = (input_tokens / 1_000_000) * input_cost_per_million
        output_cost = (output_tokens / 1_000_000) * output_cost_per_million
        
        total_cost = input_cost + output_cost
        
        return {
            "cost": total_cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens
        }

    async def run_agent(self, agent_type: str, input_data: dict, image_path: Optional[str] = None) -> dict:
        """Run a specific agent with input data and optional image"""
        
        if agent_type not in self.agent_configs:
            raise ValueError(f"Unknown agent type: {agent_type}")
            
        config = self.agent_configs[agent_type]
        
        try:
            # 1. Load prompt template
            prompt_template = Path(config["prompt_file"]).read_text(encoding="utf-8")
            
            # 2. Get tools from specified MCP servers (if any)
            tools_text = ""
            if config.get("mcp_servers"):
                tools = self.multi_mcp.get_tools_from_servers(config["mcp_servers"])
                if tools:
                    tool_descriptions = []
                    for tool in tools:
                        schema = tool.inputSchema
                        if "input" in schema.get("properties", {}):
                            inner_key = next(iter(schema.get("$defs", {})), None)
                            props = schema["$defs"][inner_key]["properties"]
                        else:
                            props = schema["properties"]

                        arg_types = []
                        for k, v in props.items():
                            t = v.get("type", "any")
                            arg_types.append(t)

                        signature_str = ", ".join(arg_types)
                        tool_descriptions.append(f"- `{tool.name}({signature_str})` # {tool.description}")
                    
                    tools_text = "\n\n### Available Tools\n\n" + "\n".join(tool_descriptions)

            
            # 3. Build full prompt
            current_date = datetime.now().strftime("%Y-%m-%d")
            full_prompt = f"CURRENT_DATE: {current_date}\n\n{prompt_template.strip()}{tools_text}\n\n```json\n{json.dumps(input_data, indent=2)}\n```"

            print(f"🛠️ [DEBUG] Generated Tools Text for {agent_type}:\n{tools_text}\n")

            # 📝 LOGGING: Save prompt to file for debugging
            debug_log_dir = Path("memory/debug_logs")
            debug_log_dir.mkdir(parents=True, exist_ok=True)
            (debug_log_dir / "latest_prompt.txt").write_text(f"AGENT: {agent_type}\nCONFIG: {config['prompt_file']}\n\n{full_prompt}", encoding="utf-8")
            log_step(f"🤖 {agent_type} invoked", payload={"prompt_file": config['prompt_file'], "input_keys": list(input_data.keys())}, symbol="🟦")

            # 4. Create model manager with agent's specified model
            model_manager = ModelManager(config["model"])
            
            # 5. Generate response (with or without image)
            if image_path and os.path.exists(image_path):
                log_step(f"🖼️ {agent_type} (with image)")
                image = Image.open(image_path)
                response = await model_manager.generate_content([full_prompt, image])
            else:
                response = await model_manager.generate_text(full_prompt)
            
            # 📝 LOGGING: Save raw response
            timestamp = datetime.now().strftime("%H%M%S")
            (debug_log_dir / f"{timestamp}_{agent_type}_response.txt").write_text(response, encoding="utf-8")
            (debug_log_dir / f"{timestamp}_{agent_type}_prompt.txt").write_text(full_prompt, encoding="utf-8")

            # 6. Parse JSON response dynamically
            output = parse_llm_json(response)
            log_step(f"✅ {agent_type} finished", payload={"output_keys": list(output.keys()) if isinstance(output, dict) else "raw_string"}, symbol="🟩")

            # import pdb; pdb.set_trace()
            
            # Calculate input text for costing
            input_text = str(input_data)
            
            # Calculate output text for costing
            output_text = str(output)
            
            # Calculate cost and tokens
            cost_data = self.calculate_cost(input_text, output_text)
            
            # Add cost data to result
            if isinstance(output, dict):
                output.update(cost_data)
            
            return {
                "success": True,
                "agent_type": agent_type,
                "output": output
            }
            
        except Exception as e:
            log_error(f"❌ {agent_type}: {str(e)}")
            return {
                "success": False,
                "agent_type": agent_type,
                "error": str(e),
                "cost": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0
            }

    def get_available_agents(self) -> list:
        """Return list of available agent types"""
        return list(self.agent_configs.keys())
