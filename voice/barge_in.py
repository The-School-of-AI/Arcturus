"""
voice/barge_in.py

Robust barge-in (interruption) detection for low-latency voice agents.

Design goals (per project requirements):
- Do NOT interrupt on single-frame VAD triggers.
- Require continuous speech duration (120–200ms).
- Require energy significantly above the ambient noise floor (~2.0–2.5×).
- Keep this detector *separate* from the wake/VAD/STT pipeline so we can
  hard-gate mic frames away from VAD/STT during TTS while still allowing
  barge-in detection after a short grace window.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class BargeInConfig:
    # Continuous speech requirement.
    min_continuous_speech_ms: float = 160.0  # within required 120–200ms band

    # Energy requirement relative to ambient noise floor.
    # 2.3x is a good default between 2.0–2.5x.
    energy_ratio_threshold: float = 2.0

    # Near-field gating to prevent distant talkers from barging-in:
    # Require a minimum absolute RMS AND a minimum margin above noise floor.
    # (Both are in int16 RMS units, 0–32768.)
    min_absolute_rms: float = 700.0
    min_rms_above_noise: float = 200.0

    # Absolute RMS floor to avoid division-by-near-zero or hypersensitivity
    # when noise floor hasn't been established yet.
    min_noise_floor_rms: float = 50.0  # int16 RMS scale

    # Noise floor estimator smoothing (only updated when NOT speaking).
    noise_floor_alpha: float = 0.03


class BargeInDetector:
    """
    Two-phase usage:
      1) During IDLE/LISTENING/THINKING: call observe_ambient(pcm) to
         update the noise floor estimate.
      2) During SPEAKING (after grace): call should_interrupt(pcm) to
         decide whether to interrupt TTS. This does NOT update noise floor.
    """

    def __init__(self, sample_rate: int, frame_length: int, config: BargeInConfig | None = None):
        self.sample_rate = int(sample_rate)
        self.frame_length = int(frame_length)
        self.cfg = config or BargeInConfig()

        self._frame_ms = (self.frame_length / self.sample_rate) * 1000.0

        self._noise_floor_rms = self.cfg.min_noise_floor_rms
        self._speech_ms = 0.0

    @property
    def noise_floor_rms(self) -> float:
        return float(self._noise_floor_rms)

    @property
    def speech_ms(self) -> float:
        return float(self._speech_ms)

    def reset_speech_streak(self) -> None:
        self._speech_ms = 0.0

    def observe_ambient(self, pcm_frame: Iterable[int]) -> float:
        """
        Update ambient noise floor estimate from a mic frame.
        Call this only when NOT speaking, so TTS echo doesn't contaminate the floor.

        Returns:
            rms (int16-scale)
        """
        rms = _rms_int16(pcm_frame)
        # Exponential moving average, but avoid "learning" user speech as noise.
        alpha = self.cfg.noise_floor_alpha
        nf = self._noise_floor_rms
        learnable = rms <= max(self.cfg.min_noise_floor_rms, nf * 1.5)
        if learnable:
            # Clamp to a minimum so we don't go to ~0 in silence.
            new_nf = max(self.cfg.min_noise_floor_rms, (1.0 - alpha) * nf + alpha * rms)
            self._noise_floor_rms = new_nf
        return rms

    def should_interrupt(self, pcm_frame: Iterable[int]) -> tuple[bool, float, float]:
        """
        Decide whether the user is barging-in.

        Requirements implemented:
        - Continuous speech >= min_continuous_speech_ms
        - RMS energy >= energy_ratio_threshold × noise_floor

        Returns:
            (interrupt, rms, ratio)
        """
        rms = _rms_int16(pcm_frame)
        nf = max(self.cfg.min_noise_floor_rms, self._noise_floor_rms)
        ratio = (rms / nf) if nf > 0 else 0.0

        required_rms = max(
            self.cfg.min_absolute_rms,
            nf * self.cfg.energy_ratio_threshold,
            nf + self.cfg.min_rms_above_noise,
        )
        is_speech_frame = rms >= required_rms

        if is_speech_frame:
            self._speech_ms += self._frame_ms
        else:
            self._speech_ms = 0.0

        return (self._speech_ms >= self.cfg.min_continuous_speech_ms), rms, ratio


def _rms_int16(pcm_frame) -> float:
    """
    Compute RMS on an int16 PCM frame. Returns RMS in int16 units (0–32768).
    Accepts numpy arrays (fast path) or any iterable of ints (fallback).
    """
    if isinstance(pcm_frame, np.ndarray):
        arr = pcm_frame.astype(np.float64)
    else:
        arr = np.array(pcm_frame, dtype=np.float64)
    if arr.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(arr * arr)))


