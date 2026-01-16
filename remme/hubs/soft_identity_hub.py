"""
SoftIdentityHub - Low-stakes personalization signals.

Manages soft personalization for examples and analogies:
- Food preferences
- Pet affinity
- Media tastes
- Communication style
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from remme.hubs.base_hub import BaseHub
from remme.schemas.hub_schemas import SoftIdentityHubSchema


class SoftIdentityHub(BaseHub):
    """
    Soft identity hub for personalization signals.
    
    Stores low-stakes preferences used for examples, analogies, and casual
    recommendations. Must never affect tool selection or risk decisions.
    """
    
    SCHEMA_CLASS = SoftIdentityHubSchema
    DEFAULT_PATH = "memory/user_model/soft_identity_hub.json"
    
    def __init__(self, path: Optional[Path] = None):
        super().__init__(path)
    
    # =========================================================================
    # RETRIEVAL METHODS
    # =========================================================================
    
    def get_dietary_style(self) -> Optional[str]:
        """Get dietary style preference."""
        return self.data.food_and_dining.dietary_style.value
    
    def get_cuisine_likes(self) -> List[str]:
        """Get liked cuisines."""
        return self.data.food_and_dining.cuisine_affinities.likes or []
    
    def get_pet_affinity(self) -> Optional[str]:
        """Get pet affinity (dog/cat/both/neither)."""
        return self.data.pets_and_animals.affinity.value
    
    def get_humor_tolerance(self) -> Optional[str]:
        """Get humor tolerance level."""
        return self.data.communication_style.humor_tolerance.value
    
    def get_small_talk_tolerance(self) -> Optional[str]:
        """Get small talk tolerance level."""
        return self.data.communication_style.small_talk_tolerance.value
    
    def get_music_genres(self) -> List[str]:
        """Get liked music genres."""
        return self.data.media_and_entertainment.music.genres or []
    
    def get_professional_interests(self) -> List[str]:
        """Get professional interests."""
        return self.data.interests_and_hobbies.professional_interests or []
    
    def get_experience_level(self) -> Optional[str]:
        """Get professional experience level."""
        return self.data.professional_context.experience_level.value
    
    def get_allowed_usage(self) -> List[str]:
        """Get contexts where soft identity can be used."""
        return self.data.usage_rules.allowed_in or []
    
    def get_never_affects(self) -> List[str]:
        """Get contexts where soft identity must NOT be used."""
        return self.data.usage_rules.never_affects or []
    
    def get_personalization_context(self) -> Dict[str, Any]:
        """
        Get personalization context for casual interactions.
        
        Only includes fields with sufficient confidence.
        """
        context = {}
        
        # Food (if confident)
        if self.data.food_and_dining.dietary_style.confidence > 0.3:
            context["dietary_style"] = self.get_dietary_style()
        if self.data.food_and_dining.cuisine_affinities.confidence > 0.3:
            context["cuisine_likes"] = self.get_cuisine_likes()[:3]
        
        # Pets
        if self.data.pets_and_animals.affinity.confidence > 0.3:
            context["pet_affinity"] = self.get_pet_affinity()
        
        # Communication
        if self.data.communication_style.humor_tolerance.confidence > 0.3:
            context["humor_tolerance"] = self.get_humor_tolerance()
        if self.data.communication_style.small_talk_tolerance.confidence > 0.3:
            context["small_talk_tolerance"] = self.get_small_talk_tolerance()
        
        # Interests
        interests = self.get_professional_interests()
        if interests:
            context["interests"] = interests[:5]
        
        return context
    
    def get_compact_policy(self, scope: str = "general") -> str:
        """Get compact summary for prompt injection."""
        lines = []
        
        pet = self.get_pet_affinity()
        if pet and pet != "unknown":
            lines.append(f"Pet preference: {pet}")
        
        humor = self.get_humor_tolerance()
        if humor:
            lines.append(f"Humor tolerance: {humor}")
        
        interests = self.get_professional_interests()[:3]
        if interests:
            lines.append(f"Interests: {', '.join(interests)}")
        
        if not lines:
            return "Soft identity: Limited data"
        
        return "\n".join(lines)
    
    # =========================================================================
    # UPDATE METHODS
    # =========================================================================
    
    def set_dietary_style(self, value: str):
        """Set dietary style preference."""
        self.data.food_and_dining.dietary_style.value = value
        self.data.food_and_dining.dietary_style.confidence = 0.5
        self.data.food_and_dining.dietary_style.last_seen_at = datetime.now()
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"🍽️ Set dietary style = {value}")
    
    def add_cuisine_like(self, cuisine: str):
        """Add a liked cuisine."""
        likes = self.data.food_and_dining.cuisine_affinities.likes
        if cuisine not in likes:
            likes.append(cuisine)
            self.data.food_and_dining.cuisine_affinities.confidence = min(
                0.7, self.data.food_and_dining.cuisine_affinities.confidence + 0.1
            )
            self.data.food_and_dining.cuisine_affinities.last_seen_at = datetime.now()
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🍜 Added liked cuisine: {cuisine}")
    
    def add_cuisine_dislike(self, cuisine: str):
        """Add a disliked cuisine."""
        dislikes = self.data.food_and_dining.cuisine_affinities.dislikes
        if cuisine not in dislikes:
            dislikes.append(cuisine)
            self.data.food_and_dining.cuisine_affinities.last_seen_at = datetime.now()
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🚫 Added disliked cuisine: {cuisine}")
    
    def set_pet_affinity(self, value: str):
        """Set pet affinity."""
        self.data.pets_and_animals.affinity.value = value
        self.data.pets_and_animals.affinity.confidence = 0.5
        self.data.pets_and_animals.affinity.last_seen_at = datetime.now()
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"🐾 Set pet affinity = {value}")
    
    def set_humor_tolerance(self, value: str):
        """Set humor tolerance level."""
        self.data.communication_style.humor_tolerance.value = value
        self.data.communication_style.humor_tolerance.confidence = 0.4
        self.data.communication_style.humor_tolerance.last_seen_at = datetime.now()
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"😄 Set humor tolerance = {value}")
    
    def set_small_talk_tolerance(self, value: str):
        """Set small talk tolerance level."""
        self.data.communication_style.small_talk_tolerance.value = value
        self.data.communication_style.small_talk_tolerance.confidence = 0.4
        self.data.communication_style.small_talk_tolerance.last_seen_at = datetime.now()
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"💬 Set small talk tolerance = {value}")
    
    def add_professional_interest(self, interest: str):
        """Add a professional interest."""
        interests = self.data.interests_and_hobbies.professional_interests
        if interest not in interests:
            interests.append(interest)
            self.data.interests_and_hobbies.confidence = min(
                0.7, self.data.interests_and_hobbies.confidence + 0.1
            )
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"💼 Added professional interest: {interest}")
    
    def add_hobby(self, hobby: str):
        """Add a personal hobby."""
        hobbies = self.data.interests_and_hobbies.personal_hobbies
        if hobby not in hobbies:
            hobbies.append(hobby)
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🎯 Added hobby: {hobby}")
    
    def add_music_genre(self, genre: str):
        """Add a liked music genre."""
        genres = self.data.media_and_entertainment.music.genres
        if genre not in genres:
            genres.append(genre)
            self.data.media_and_entertainment.music.confidence = min(
                0.6, self.data.media_and_entertainment.music.confidence + 0.1
            )
            self.data.meta.evidence_count += 1
            self._update_confidence()
            print(f"🎵 Added music genre: {genre}")
    
    def set_experience_level(self, value: str):
        """Set professional experience level."""
        self.data.professional_context.experience_level.value = value
        self.data.professional_context.experience_level.confidence = 0.5
        self.data.meta.evidence_count += 1
        self._update_confidence()
        print(f"📈 Set experience level = {value}")


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================

_hub: Optional[SoftIdentityHub] = None


def get_soft_identity_hub() -> SoftIdentityHub:
    """Get or create the global SoftIdentityHub instance."""
    global _hub
    if _hub is None:
        _hub = SoftIdentityHub()
    return _hub
