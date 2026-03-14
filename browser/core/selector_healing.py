"""
Semantic Selector Healing

When CSS/XPath selectors fail due to page redesigns:
- Re-interpret current page to understand semantic change
- Derive new selector via semantic reasoning
- Use ARIA labels, visual position, element role
- Self-healing automations

Example:
- Old selector: "#export-btn" (ID changed)
- New selector: "button[aria-label='Export Data']" (semantic recovery)
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import re


@dataclass
class SelectorMatch:
    """Represents a matched element"""
    element_id: str
    tag: str
    classes: List[str]
    aria_label: Optional[str]
    aria_role: Optional[str]
    text_content: str
    xpath: str
    css_selector: Optional[str]
    confidence: float  # 0.0-1.0


class SelectorHealer:
    """
    Heals broken selectors through semantic reasoning.
    
    When a selector fails, instead of trying mechanical alternatives,
    understand what changed and derive new selector semantically.
    """
    
    def __init__(self):
        self.selector_mappings: Dict[str, str] = {}  # old -> new
        self.healing_attempts: List[Dict] = []
    
    def heal_selector(
        self,
        original_selector: str,
        page_elements: List[Dict],
        semantic_goal: str,
    ) -> Tuple[Optional[str], float]:
        """
        Heal a broken selector through semantic reasoning.
        
        Args:
            original_selector: CSS/XPath selector that failed
            page_elements: List of page elements (with attributes)
            semantic_goal: What the selector should target (e.g., "export button")
        
        Returns:
            (new_selector, confidence) or (None, 0.0) if healing failed
        """
        # Try to extract semantic intent from original selector
        intent = self._extract_intent(original_selector)
        
        # Search for elements matching semantic goal
        candidates = self._find_semantic_matches(
            page_elements,
            semantic_goal,
            intent,
        )
        
        if not candidates:
            return None, 0.0
        
        # Select best match (highest confidence)
        best_match = max(candidates, key=lambda x: x['confidence'])
        
        # Build new selector
        new_selector = self._build_selector(best_match)
        confidence = best_match['confidence']
        
        # Cache for future use
        self.selector_mappings[original_selector] = new_selector
        
        self.healing_attempts.append({
            'original': original_selector,
            'new': new_selector,
            'goal': semantic_goal,
            'confidence': confidence,
        })
        
        return new_selector, confidence
    
    def _extract_intent(self, selector: str) -> Dict[str, str]:
        """Extract semantic intent from selector"""
        intent = {}
        
        # Extract class names
        classes = re.findall(r'\.([a-zA-Z0-9_-]+)', selector)
        if classes:
            intent['classes'] = classes
        
        # Extract ID
        id_match = re.search(r'#([a-zA-Z0-9_-]+)', selector)
        if id_match:
            intent['id'] = id_match.group(1)
        
        # Extract tag
        tag_match = re.match(r'^([a-zA-Z]+)', selector)
        if tag_match:
            intent['tag'] = tag_match.group(1)
        
        # Extract text patterns
        text_match = re.search(r'["\']([^"\']+)["\']', selector)
        if text_match:
            intent['text'] = text_match.group(1)
        
        return intent
    
    def _find_semantic_matches(
        self,
        page_elements: List[Dict],
        goal: str,
        original_intent: Dict[str, str],
    ) -> List[Dict]:
        """
        Find page elements matching semantic goal.
        
        Args:
            page_elements: Available page elements
            goal: Semantic goal (e.g., "export button")
            original_intent: Intent extracted from original selector
        
        Returns:
            List of candidate matches with confidence scores
        """
        candidates = []
        goal_lower = goal.lower()
        
        for element in page_elements:
            confidence = 0.0
            reasons = []
            
            # Check ARIA labels (highest confidence)
            if 'aria_label' in element:
                aria_label = element['aria_label'].lower()
                if self._semantic_match(aria_label, goal):
                    confidence += 0.4
                    reasons.append("ARIA label match")
            
            # Check text content
            if 'text' in element:
                text = element['text'].lower()
                if self._semantic_match(text, goal):
                    confidence += 0.3
                    reasons.append("Text content match")
            
            # Check element role
            if 'role' in element:
                role = element['role'].lower()
                if self._role_matches_goal(role, goal):
                    confidence += 0.2
                    reasons.append("Role match")
            
            # Check for visual proximity to original position
            if 'position' in element and 'position' in original_intent:
                # Estimate proximity score
                confidence += 0.1
                reasons.append("Position proximity")
            
            if confidence > 0.3:  # Minimum threshold
                candidates.append({
                    'element': element,
                    'confidence': min(confidence, 1.0),
                    'reasons': reasons,
                })
        
        return candidates
    
    def _semantic_match(self, source: str, target: str) -> bool:
        """Check if source semantically matches target"""
        source_lower = source.lower()
        target_lower = target.lower()
        
        # Exact or substring match
        if target_lower in source_lower or source_lower in target_lower:
            return True
        
        # Synonym matching
        synonyms = {
            'export': ['download', 'save', 'extract'],
            'delete': ['remove', 'trash', 'discard'],
            'save': ['submit', 'confirm', 'store'],
            'back': ['previous', 'go back', 'return'],
        }
        
        target_word = target_lower.split()[0]
        if target_word in synonyms:
            for synonym in synonyms[target_word]:
                if synonym in source_lower:
                    return True
        
        return False
    
    def _role_matches_goal(self, role: str, goal: str) -> bool:
        """Check if element role matches goal"""
        role_lower = role.lower()
        goal_lower = goal.lower()
        
        if 'button' in goal_lower and role_lower in ['button', 'menuitem']:
            return True
        if 'link' in goal_lower and role_lower in ['link', 'menuitem']:
            return True
        if 'input' in goal_lower and role_lower in ['textbox', 'searchbox']:
            return True
        
        return False
    
    def _build_selector(self, match: Dict) -> str:
        """Build new selector from matched element"""
        element = match['element']
        
        # Prefer ARIA-based selectors (most stable)
        if 'aria_label' in element:
            return f"[aria-label='{element['aria_label']}']"
        
        if 'aria_role' in element:
            selector = f"[role='{element['aria_role']}']"
            # Add additional specificity if needed
            if 'text' in element:
                selector += f":contains('{element['text']}')"
            return selector
        
        # Fall back to class-based selector
        if 'classes' in element and element['classes']:
            classes = '.'.join(element['classes'][:2])  # First 2 classes
            return f".{classes}"
        
        # Last resort: XPath
        if 'xpath' in element:
            return element['xpath']
        
        # Default to tag selector
        tag = element.get('tag', 'div')
        return f"{tag}:contains('{element.get('text', '')}')"
    
    def suggest_stable_selector(self, element: Dict) -> str:
        """
        Suggest the most stable selector for an element.
        
        Ranking: ARIA > Role > Class > ID > Text > XPath
        """
        # ARIA is most stable
        if 'aria_label' in element:
            return f"[aria-label='{element['aria_label']}']"
        
        # Role-based
        if 'aria_role' in element:
            return f"[role='{element['aria_role']}']"
        
        # Class-based (usually stable)
        if 'classes' in element and element['classes']:
            return f".{element['classes'][0]}"
        
        # ID (can change, but often stable)
        if 'id' in element:
            return f"#{element['id']}"
        
        # Text content (least stable but recoverable)
        if 'text' in element:
            return f"*:contains('{element['text']}')"
        
        # XPath (most specific but can break)
        return element.get('xpath', '')
    
    def get_healing_statistics(self) -> Dict:
        """Get selector healing statistics"""
        successful = [a for a in self.healing_attempts if a['confidence'] > 0.5]
        
        return {
            'total_attempts': len(self.healing_attempts),
            'successful': len(successful),
            'success_rate': len(successful) / len(self.healing_attempts) if self.healing_attempts else 0,
            'avg_confidence': sum(a['confidence'] for a in self.healing_attempts) / len(self.healing_attempts) if self.healing_attempts else 0,
            'cached_mappings': len(self.selector_mappings),
        }
