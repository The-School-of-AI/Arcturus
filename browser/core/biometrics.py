"""
Behavioral Biometrics Simulation

Human-like input patterns to evade anti-bot detection:
- Physics-based mouse movement (Bézier curves + acceleration)
- Typing with per-character timing + think pauses
- Scroll with realistic inertia
- Defense against Cloudflare, DataDome, Imperva
"""

from typing import List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime
import random
import math
import time


@dataclass
class MouseMove:
    """Mouse movement event"""
    x: int
    y: int
    timestamp: datetime
    duration_ms: int  # Time to reach this point


@dataclass
class KeyPress:
    """Keyboard press event"""
    char: str
    timestamp: datetime
    duration_ms: int  # Time to press this key
    hold_time_ms: int  # How long key was held


class BehavioralBiometrics:
    """
    Simulates human-like input behavior to evade bot detection.
    
    Modern anti-bot systems (Cloudflare, DataDome, Imperva) analyze:
    - Mouse movement trajectories
    - Typing rhythm and pauses
    - Scroll patterns and inertia
    - Inter-event timing distributions
    - Touch pressure (mobile)
    
    This module generates realistic patterns based on statistical models.
    """
    
    def __init__(self, persona: Optional[str] = None):
        """
        Initialize biometrics simulator.
        
        Args:
            persona: Optional persona type ('careful', 'normal', 'fast')
                    affects typing speed, mouse precision, scroll behavior
        """
        self.persona = persona or 'normal'
        self._initialize_persona()
    
    def _initialize_persona(self):
        """Set behavioral parameters based on persona"""
        if self.persona == 'careful':
            self.typing_wpm = 40  # Slow, careful typing
            self.mouse_precision = 0.95  # Very precise
            self.pause_frequency = 0.3  # Frequent pauses
        elif self.persona == 'fast':
            self.typing_wpm = 80  # Fast typing
            self.mouse_precision = 0.7  # Less precise
            self.pause_frequency = 0.05  # Rare pauses
        else:  # normal
            self.typing_wpm = 60
            self.mouse_precision = 0.85
            self.pause_frequency = 0.15
    
    def generate_mouse_movement(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int,
        duration_ms: int = 500,
    ) -> List[MouseMove]:
        """
        Generate realistic mouse movement using Bézier curves.
        
        Args:
            start_x, start_y: Starting position
            end_x, end_y: Target position
            duration_ms: Time to reach target
        
        Returns:
            List of mouse position events
        """
        moves = []
        
        # Generate Bézier control points
        cp1_x = start_x + random.randint(-100, 100)
        cp1_y = start_y + random.randint(-150, 50)
        cp2_x = end_x + random.randint(-100, 100)
        cp2_y = end_y + random.randint(-50, 150)
        
        # Number of steps
        steps = max(20, duration_ms // 16)  # ~60 FPS
        
        for i in range(steps):
            t = i / steps
            
            # Cubic Bézier interpolation
            x = (
                (1-t)**3 * start_x +
                3 * (1-t)**2 * t * cp1_x +
                3 * (1-t) * t**2 * cp2_x +
                t**3 * end_x
            )
            y = (
                (1-t)**3 * start_y +
                3 * (1-t)**2 * t * cp1_y +
                3 * (1-t) * t**2 * cp2_y +
                t**3 * end_y
            )
            
            # Add small jitter for realism
            jitter_x = random.gauss(0, 0.5)
            jitter_y = random.gauss(0, 0.5)
            
            x = int(x + jitter_x)
            y = int(y + jitter_y)
            
            # Add acceleration/deceleration
            ease_factor = self._ease_out_cubic(t)
            step_duration = int(duration_ms / steps * ease_factor)
            
            moves.append(MouseMove(
                x=x,
                y=y,
                timestamp=datetime.utcnow(),
                duration_ms=step_duration,
            ))
        
        return moves
    
    def generate_typing_sequence(
        self,
        text: str,
    ) -> List[KeyPress]:
        """
        Generate realistic typing with variable rhythm.
        
        Args:
            text: Text to generate typing for
        
        Returns:
            List of key press events
        """
        key_presses = []
        current_time = datetime.utcnow()
        
        # Convert WPM to milliseconds per character
        ms_per_char = (60000 / (self.typing_wpm * 5))
        
        for i, char in enumerate(text):
            # Base typing time for this character
            if char == ' ':
                base_duration = ms_per_char * 0.8  # Spaces are faster
            elif char.isupper():
                base_duration = ms_per_char * 1.1  # Shift key adds time
            else:
                base_duration = ms_per_char
            
            # Add per-character timing variation (Gaussian distribution)
            duration = int(base_duration + random.gauss(0, base_duration * 0.15))
            
            # Hold time for key
            hold_time = random.randint(50, 150)
            
            # Random think pause (5% chance)
            if random.random() < self.pause_frequency:
                # Insert pause before character
                pause_duration = random.randint(500, 2000)
                current_time = datetime.fromtimestamp(
                    current_time.timestamp() + pause_duration / 1000
                )
            
            key_presses.append(KeyPress(
                char=char,
                timestamp=current_time,
                duration_ms=duration,
                hold_time_ms=hold_time,
            ))
            
            current_time = datetime.fromtimestamp(
                current_time.timestamp() + duration / 1000
            )
        
        return key_presses
    
    def generate_scroll_movement(
        self,
        distance_pixels: int,
        duration_ms: int = 800,
    ) -> List[Tuple[int, int]]:  # (pixels_scrolled, timestamp_offset_ms)
        """
        Generate realistic scroll with inertia.
        
        Args:
            distance_pixels: How far to scroll
            duration_ms: Duration of scroll animation
        
        Returns:
            List of (pixels, time_offset) tuples
        """
        scroll_events = []
        
        # Initial scroll velocity
        velocity = distance_pixels / duration_ms
        
        # Deceleration due to friction
        friction = 0.98
        
        current_pos = 0
        elapsed_ms = 0
        
        while elapsed_ms < duration_ms and current_pos < distance_pixels:
            # Update position with velocity
            current_pos += velocity * 16  # 16ms per frame
            
            # Apply friction
            velocity *= friction
            
            elapsed_ms += 16
            
            scroll_events.append((
                int(current_pos),
                elapsed_ms,
            ))
        
        # Ensure we reach target
        scroll_events.append((distance_pixels, duration_ms))
        
        return scroll_events
    
    def generate_click_timing(self) -> Tuple[int, int]:
        """
        Generate realistic click timing (delay before, duration).
        
        Returns:
            (reaction_time_ms, click_duration_ms)
        """
        # Human reaction time: 150-300ms
        reaction_time = random.randint(150, 300)
        
        # Click duration: 100-200ms
        click_duration = random.randint(100, 200)
        
        return reaction_time, click_duration
    
    def _ease_out_cubic(self, t: float) -> float:
        """Cubic easing function for smooth acceleration/deceleration"""
        return 1 - (1 - t) ** 3
    
    def get_persona_fingerprint(self) -> dict:
        """Get fingerprint of this behavioral persona"""
        return {
            'typing_wpm': self.typing_wpm,
            'mouse_precision': self.mouse_precision,
            'pause_frequency': self.pause_frequency,
            'persona': self.persona,
        }
    
    @staticmethod
    def generate_realistic_delay() -> int:
        """
        Generate realistic inter-action delay.
        
        Returns:
            Delay in milliseconds
        """
        # Exponential distribution with mean of 800ms
        return int(random.expovariate(1/800) * 1000)
    
    @staticmethod
    def is_pattern_detectable(
        mouse_moves: Optional[List] = None,
        key_presses: Optional[List] = None,
    ) -> bool:
        """
        Estimate if generated pattern might be detected as bot.
        
        This is a heuristic; real detection involves ML models.
        """
        # Check for suspiciously perfect patterns
        if mouse_moves:
            # All moves same duration = suspicious
            durations = [m.duration_ms for m in mouse_moves]
            if len(set(durations)) == 1:
                return True
        
        if key_presses:
            # All keys same timing = suspicious
            durations = [k.duration_ms for k in key_presses]
            if len(set(durations)) == 1:
                return True
        
        return False
