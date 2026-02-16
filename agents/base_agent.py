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
        # Config loading is now handled by core.bootstrap and AgentRegistry
        # We lazy-load on first run if needed.
    
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

    async def run_agent(self, agent_type: str, input_data: dict, image_path: Optional[str] = None, use_system2: bool = False) -> dict:
        """Run a specific agent with input data and optional image. use_system2=True enables Reasoning Loop."""
        
        from core.registry import AgentRegistry
        config = AgentRegistry.get(agent_type)
        
        if not config:
            # Lazy bootstrap if registry is empty or agent missing
            from core.bootstrap import bootstrap_agents
            bootstrap_agents()
            config = AgentRegistry.get(agent_type)
            
        if not config:
            raise ValueError(f"Unknown agent type: {agent_type} (Not found in Registry)")
        
        try:
            # 1. Load prompt template
            if "prompt_text" in config:
                prompt_template = config["prompt_text"]
            elif "prompt_file" in config:
                prompt_template = Path(config["prompt_file"]).read_text(encoding="utf-8")
            else:
                 prompt_template = f"You are {agent_type}. No specific prompt provided."

            # 🧩 SKILLS INJECTION
            skill_tools_list = []
            try:
                from shared.state import get_skill_manager
                skill_manager = get_skill_manager()
                
                # 1. Load Configured Skills
                active_skills = []
                for skill_name in config.get("skills", []):
                    skill = skill_manager.get_skill(skill_name)
                    if skill:
                        active_skills.append(skill)
                        
                # 2. Apply Skills
                skill_prompts = []
                for skill in active_skills:
                    meta = skill.get_metadata()
                    
                    # Get prompt additions
                    additions = skill.get_system_prompt_additions()
                    if additions:
                        skill_prompts.append(additions)
                    
                    # Get tools from skill
                    skill_tools_list.extend(skill.get_tools())
                    
                    log_step(f"🧩 Applied Skill: {meta.name}", symbol="🧩")
                
                if skill_prompts:
                    # Append skill prompts to the main prompt template
                    prompt_template = prompt_template.strip() + "\n\n" + "\n\n".join(skill_prompts)
                    
            except Exception as e:
                log_error(f"Failed to inject skills: {e}")

            # 2. Get tools from specified MCP servers (if any)
            tools_text = ""
            all_tools = []
            
            if config.get("mcp_servers"):
                mcp_tools = self.multi_mcp.get_tools_from_servers(config["mcp_servers"])
                if mcp_tools:
                    all_tools.extend(mcp_tools)
            
            # Combine with skill tools
            if skill_tools_list:
                all_tools.extend(skill_tools_list)

            if all_tools:
                tool_descriptions = []
                for tool in all_tools:
                    # Simple documentation of tool
                    # Check if it has a schema or is a simple func
                    if hasattr(tool, 'inputSchema'):
                        schema = tool.inputSchema
                        # ... existing parsing logic ...
                        if "input" in schema.get("properties", {}):
                            inner_key = next(iter(schema.get("$defs", {})), None)
                            props = schema["$defs"][inner_key]["properties"] if inner_key else {}
                        else:
                            props = schema.get("properties", {})

                        arg_types = []
                        for k, v in props.items():
                            t = v.get("type", "any")
                            arg_types.append(t)
                        signature_str = ", ".join(arg_types)
                        tool_descriptions.append(f"- `{tool.name}({signature_str})` # {tool.description}")
                    else:
                        # Fallback for non-MCP tools
                        tool_descriptions.append(f"- `{getattr(tool, 'name', 'tool')}` # {getattr(tool, 'description', 'No description')}")
                
                tools_text = "\n\n### Available Tools\n\n" + "\n".join(tool_descriptions)

            # 3. Build context (Date, Preferences, Registry)
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # 3a. Inject user preferences (compact format)
            try:
                from remme.preferences import get_compact_policy
                scope_map = {
                    "PlannerAgent": "planning", "CoderAgent": "coding",
                    "DistillerAgent": "coding", "FormatterAgent": "formatting",
                    "RetrieverAgent": "research", "ThinkerAgent": "reasoning",
                }
                scope = scope_map.get(agent_type, "general")
                user_prefs_text = f"\n---\n## User Preferences\n{get_compact_policy(scope)}\n---\n"
            except Exception:
                user_prefs_text = ""
            
            # 3b. Inject Available Agents (for Planner abstraction)
            if "{available_agents_enum}" in prompt_template or "{available_agents_description}" in prompt_template:
                from core.registry import AgentRegistry
                agents_dict = AgentRegistry.list_agents()
                enum_str = ' | '.join([f'"{name}"' for name in agents_dict.keys()])
                desc_lines = []
                for name, desc in agents_dict.items():
                    clean_desc = desc.strip()
                    if "\n" in clean_desc:
                         lines = clean_desc.split("\n")
                         formatted_desc = lines[0] + "\n" + "\n".join([f"  {line}" for line in lines[1:]])
                         desc_lines.append(f"* **{name}**: {formatted_desc}")
                    else:
                         desc_lines.append(f"* **{name}**: {clean_desc}")
                desc_str = "\n".join(desc_lines)
                prompt_template = prompt_template.replace("{available_agents_enum}", enum_str)
                prompt_template = prompt_template.replace("{available_agents_description}", desc_str)

            # 3c. Inject Episodic Memory (JitRL) for PlannerAgent
            episodic_context = ""
            if agent_type == "PlannerAgent":
                try:
                    from memory.episodic import search_episodes
                    # Handle different input key possibilities
                    query = input_data.get("task") or input_data.get("original_query") or ""
                    if query:
                        log_step(f"🧠 Searching episodic memory for: '{query[:50]}...'", symbol="🔍")
                        past_episodes = search_episodes(query, limit=2)
                        if past_episodes:
                            episodic_context = "\n\n## Relevant Past Experiences (Recipes)\n"
                            episodic_context += "Use these successful past workflows as inspiration for your new plan:\n"
                            for ep in past_episodes:
                                steps = " -> ".join([n.get("agent", "??") for n in ep.get("nodes", []) if n.get("agent") != "System"])
                                episodic_context += f"- **Task**: \"{ep['original_query']}\"\n  **Workflow**: {steps}\n"
                            log_step(f"📈 Found {len(past_episodes)} relevant past episodes.", symbol="💡")
                except Exception as e:
                    log_error(f"Episodic retrieval hook failed: {e}")

            # 3d. Inject Factual Memory (Semantic Injection)
            factual_context = ""
            if agent_type in ["SummarizerAgent", "RetrieverAgent", "CoderAgent"]:
                try:
                    from memory.mem0_store import MemoryStore
                    store = MemoryStore()
                    query = input_data.get("task") or input_data.get("original_query") or ""
                    if query:
                        facts = store.search(query, limit=3)
                        if facts:
                            factual_context = "\n\n## Memories of User Preferences & Facts\n"
                            factual_context += "Use these stored facts to inform your response:\n"
                            for f in facts:
                                if isinstance(f, dict):
                                    factual_context += f"- {f.get('memory', f.get('content', str(f)))}\n"
                                else:
                                    factual_context += f"- {str(f)}\n"
                except Exception as e:
                    log_error(f"Factual memory hook failed: {e}")

            # 3e. Inject System Profile (Cortex-R settings)
            profile_context = ""
            try:
                from core.profile_loader import get_profile
                profile = get_profile()
                biases = profile.biases
                profile_context = f"\n---\n## System Profile\n- Tone: {biases['tone']}\n- Verbosity: {biases['verbosity']}\n---\n"
            except Exception as e:
                log_error(f"Profile injection failed: {e}")

            # 4. Final Prompt Construction
            full_prompt = f"CURRENT_DATE: {current_date}\n\n{prompt_template.strip()}{user_prefs_text}{profile_context}{episodic_context}{factual_context}{tools_text}\n\n```json\n{json.dumps(input_data, indent=2, default=str)}\n```"
            
            print(f"🛠️ [DEBUG] Generated Tools Text for {agent_type}:\n{tools_text}\n")

            debug_log_dir = Path(__file__).parent.parent / "memory" / "debug_logs"
            debug_log_dir.mkdir(parents=True, exist_ok=True)
            (debug_log_dir / "latest_prompt.txt").write_text(f"AGENT: {agent_type}\nCONFIG: {config.get('prompt_file', 'Dynamic Injection')}\n\n{full_prompt}", encoding="utf-8")
            log_step(f"🤖 {agent_type} invoked", payload={"prompt_file": config.get('prompt_file', 'Dynamic'), "input_keys": list(input_data.keys())}, symbol="🟦")

            # 4. Create model manager with user's selected model from settings
            # IMPORTANT: Use reload_settings() to get fresh settings from disk
            from config.settings_loader import reload_settings
            fresh_settings = reload_settings()
            agent_settings = fresh_settings.get("agent", {})
            
            # Check for per-agent overrides
            overrides = agent_settings.get("overrides", {})
            if agent_type in overrides:
                override = overrides[agent_type]
                model_provider = override.get("model_provider", "gemini")
                model_name = override.get("model", "gemini-2.5-flash")
                log_step(f"🎯 Override for {agent_type}: {model_provider}:{model_name}", symbol="✨")
            else:
                model_provider = agent_settings.get("model_provider", "gemini")
                model_name = agent_settings.get("default_model", "gemini-2.5-flash")
            
            log_step(f"📡 Using {model_provider}:{model_name}", symbol="🔌")
            model_manager = ModelManager(model_name, provider=model_provider)
            
            # 5. Generate response (System 1 vs System 2)
            async def generate_draft():
                if image_path and os.path.exists(image_path):
                    image = Image.open(image_path)
                    return await model_manager.generate_content([full_prompt, image])
                return await model_manager.generate_text(full_prompt)

            if use_system2:
                from core.reasoning import ReasoningEngine
                log_step("🧠 System 2 Reasoning Activated", symbol="🧠")
                engine = ReasoningEngine(model_manager)
                # We use the original query from input_data, or fallback to 'Task'
                query_context = input_data.get("original_query") or input_data.get("task") or "Complex Task"
                response, reasoning_history = await engine.run_loop(
                    query=query_context,
                    generate_func=generate_draft,
                    context=full_prompt[:1000] # Truncate context to save verification tokens
                )
            else:
                response = await generate_draft()
                reasoning_history = []
            
            # 📝 LOGGING: Save raw response
            timestamp = datetime.now().strftime("%H%M%S")
            (debug_log_dir / f"{timestamp}_{agent_type}_response.txt").write_text(response, encoding="utf-8")
            (debug_log_dir / f"{timestamp}_{agent_type}_prompt.txt").write_text(full_prompt, encoding="utf-8")

            # 6. Parse JSON response dynamically
            output = parse_llm_json(response)
            
            # Robustness: Some models (like gemma3) wrap JSON in a list
            if isinstance(output, list) and len(output) > 0 and isinstance(output[0], dict):
                output = output[0]
                
            log_step(f"🟩 {agent_type} finished", payload={"output_keys": list(output.keys()) if isinstance(output, dict) else "raw_string"}, symbol="🟩")

            # import pdb; pdb.set_trace()
            
            # Calculate input text for costing
            input_text = str(input_data)
            
            # Calculate output text for costing
            output_text = str(output)
            
            # Calculate cost and tokens
            cost_data = self.calculate_cost(input_text, output_text)
            
            # Add cost data and model info to result
            if isinstance(output, dict):
                output.update(cost_data)
                output["executed_model"] = f"{model_provider}:{model_name}"
                if reasoning_history:
                     output["_reasoning_trace"] = reasoning_history
            
            return {
                "success": True,
                "agent_type": agent_type,
                "output": output,
                "agent_prompt": full_prompt # For Episodic Memory
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
        from core.registry import AgentRegistry
        agents = list(AgentRegistry.list_agents().keys())
        if not agents:
            from core.bootstrap import bootstrap_agents
            bootstrap_agents()
            agents = list(AgentRegistry.list_agents().keys())
        return agents
