
from core.skills.base import Skill
from typing import List, Any

class RAGSkill(Skill):
    name = "rag"
    description = "Provides RAG capabilities and the search_knowledge_base tool."
    
    def get_system_prompt_additions(self) -> str:
        return "You have access to a RAG system. Use search_knowledge_base(query) to find internal documents."

    def get_tools(self) -> List[Any]:
        # Define a mock tool object that has 'name' and 'description' 
        # for our basic AgentRunner simple tool documentation.
        class RAGTool:
            name = "search_knowledge_base"
            description = "Search through uploaded and internal documents for relevant info."
            
            @property
            def inputSchema(self):
                return {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"}
                    }
                }
        
        return [RAGTool()]
