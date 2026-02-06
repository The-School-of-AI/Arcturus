import asyncio
import re
from typing import Callable, Any, Dict, List, Optional
from core.model_manager import ModelManager
from core.utils import log_step, log_error

class Verifier:
    """
    Lightweight verifier that scores and critiques agent outputs.
    Uses a specialized 'verifier' role model (e.g., small local model).
    """
    def __init__(self):
        # Initialize with strict 'verifier' role - ModelManager will enforce local/cloud policy
        try:
            # FORCE GEMINI for stability during emergency remediation
            self.model_manager = ModelManager("gemini-2.5-flash-lite", provider="gemini")
        except Exception as e:
            log_error(f"⚠️ Verifier model failed to load (Role: verifier): {e}. Falling back to Gemini Flash.")
            try:
                self.model_manager = ModelManager("gemini-2.5-flash", provider="gemini")
            except Exception as e2:
                 log_error(f"⚠️ Fallback Verifier failed: {e2}. Verification will be skipped.")
                 self.model_manager = None
        
    async def verify(self, query: str, draft: str, context: str = "") -> tuple[int, str]:
        """
        Analyze a draft response and return a score (0-100) and critique.
        """
        if not self.model_manager:
            return 100, "Verification skipped (Model unavailable)"

        prompt = f"""
        [TASK]
        You are a quality assurance verifier. 
        Evaluate the following AI response against the user's query.
        
        [USER QUERY]
        {query}
        
        [CONTEXT]
        {context}
        
        [CANDIDATE RESPONSE]
        {draft}
        
        [INSTRUCTIONS]
        1. Score the response from 0 to 100 based on correctness, completeness, and safety.
        2. Provide specific, constructive critique on what is wrong or missing.
        3. Output strict format: "SCORE: <number>\nCRITIQUE: <text>"
        """
        
        try:
            response = await self.model_manager.generate_text(prompt)
            
            # Parse output
            score_match = re.search(r"SCORE:\s*(\d+)", response, re.IGNORECASE)
            critique_match = re.search(r"CRITIQUE:\s*(.*)", response, re.IGNORECASE | re.DOTALL)
            
            score = int(score_match.group(1)) if score_match else 0
            critique = critique_match.group(1).strip() if critique_match else response
            
            return score, critique
            
        except Exception as e:
            log_error(f"Verification failed: {e}")
            return 50, f"Verification failed: {e}"

class ReasoningEngine:
    """
    Implements System 2 'Slow Thinking' via Draft-Verify-Refine loop.
    """
    def __init__(self, model_manager: ModelManager):
        self.verifier = Verifier()
        self.generator_mm = model_manager # The main agent's model manager
        
    async def run_loop(
        self, 
        query: str, 
        generate_func: Callable[..., Any], 
        context: str = "",
        max_refinements: int = 2
    ) -> tuple[str, List[Dict]]:
        """
        Execute the reasoning loop.
        
        Args:
            query: Original user intent.
            generate_func: Async function that produces a draft (str).
            context: Additional context for verification.
            max_refinements: Max attempts to improve.
        """
        
        # 1. GENERATE DRAFT
        log_step("🤔 System 2: Generating Initial Draft...", symbol="💭")
        current_draft = await generate_func()
        
        # Fast Path Check? (Optional, maybe for simple queries we skip reasoning entirely, 
        # but here we assume we are already in 'Reasoning Mode')
        
        history = []
        
        for i in range(max_refinements + 1):
            # 2. VERIFY
            score, critique = await self.verifier.verify(query, current_draft, context)
            history.append({"draft": current_draft, "score": score, "critique": critique})
            
            log_step(f"🧐 Verification Round {i+1}: Score {score}/100", symbol="🛡️")
            
            # 3. DECIDE
            if score >= 85:
                log_step("✅ Draft Accepted via Fast Path", symbol="🚀")
                return current_draft, history
            
            if i == max_refinements:
                log_step("⚠️ Max refinements reached. Returning best available draft.", symbol="🛑")
                # Return best draft seen so far
                best_attempt = max(history, key=lambda x: x['score'])
                return best_attempt['draft'], history
            
            # 4. REFINE
            log_step(f"🔧 Refining Draft (Critique: {critique[:50]}...)", symbol="🔧")
            
            refinement_prompt = f"""
            [ORIGINAL QUERY]
            {query}
            
            [PREVIOUS DRAFT]
            {current_draft}
            
            [CRITIQUE]
            {critique}
            
            [TASK]
            Rewrite the draft to address the critique and improve quality.
            Return ONLY the improved draft.
            """
            
            # We use the generator model (Main Agent) to refine its own work
            current_draft = await self.generator_mm.generate_text(refinement_prompt)

        return current_draft, history
