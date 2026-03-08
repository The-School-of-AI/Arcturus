# voice/audio_preprocess.py
"""
Lightweight audio preprocessing for better wake-word and STT accuracy.

- AGC (Automatic Gain Control): normalizes volume so quiet speech is boosted
  and loud speech is attenuated. Improves consistency for both wake detection
  and transcription in varying mic distances and environments.
- Noise gate (optional): zeros frames below a threshold to avoid feeding
  pure silence/noise into the wake engine; reduces false triggers and CPU.
"""

import math
from typing import Sequence, Tuple, Union


def _rms_int16(samples: Sequence[Union[int, float]]) -> float:
    """RMS of int16 samples (0–32768 scale)."""
    n = len(samples)
    if n == 0:
        return 0.0
    s2 = sum(float(x) * float(x) for x in samples)
    return math.sqrt(s2 / n)


def agc(
    pcm: Union[Tuple[int, ...], list],
    target_rms: float = 2000.0,
    max_gain: float = 3.0,
    min_rms_to_adjust: float = 50.0,
) -> Tuple[int, ...]:
    """
    Apply automatic gain control to a single frame of int16 PCM.

    Frames quieter than target_rms are amplified (up to max_gain); louder
    frames are attenuated. Frames with RMS below min_rms_to_adjust are
    left unchanged (avoids boosting silence/noise).
    """
    rms = _rms_int16(pcm)
    if rms < min_rms_to_adjust:
        return tuple(pcm) if not isinstance(pcm, tuple) else pcm
    gain = target_rms / rms
    gain = min(max_gain, max(0.1, gain))
    out = []
    for x in pcm:
        y = int(round(float(x) * gain))
        if y > 32767:
            y = 32767
        elif y < -32768:
            y = -32768
        out.append(y)
    return tuple(out)


def noise_gate(
    pcm: Union[Tuple[int, ...], list],
    threshold_rms: float,
) -> Union[Tuple[int, ...], None]:
    """
    Return frame unchanged if RMS >= threshold_rms, else return None.
    Use a low threshold (e.g. 100–300) so real speech passes.
    """
    rms = _rms_int16(pcm)
    if rms >= threshold_rms:
        return tuple(pcm) if not isinstance(pcm, tuple) else pcm
    return None
