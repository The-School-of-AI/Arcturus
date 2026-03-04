# Piper TTS Voice Models

## Setup

1. Download a Piper voice model from:
   https://huggingface.co/rhasspy/piper-voices

2. Recommended model for English:
   - **en_US-lessac-medium** — Good quality, fast synthesis
   - Download both files:
     - `en_US-lessac-medium.onnx`
     - `en_US-lessac-medium.onnx.json`

3. Place both files in this directory:
   ```
   voice/piper_models/
   ├── en_US-lessac-medium.onnx
   └── en_US-lessac-medium.onnx.json
   ```

4. Update `voice/config.py` if using a different model:
   ```python
   "piper_tts": {
       "model_path": os.path.join(_VOICE_DIR, "piper_models", "your_model.onnx"),
       ...
   }
   ```

## Alternative Models

| Model | Quality | Speed | Size |
|-------|---------|-------|------|
| en_US-lessac-low | Low | Fastest | ~16MB |
| en_US-lessac-medium | Medium | Fast | ~64MB |
| en_US-lessac-high | High | Moderate | ~107MB |
| en_US-amy-medium | Medium | Fast | ~64MB |
| en_GB-alba-medium | Medium (British) | Fast | ~64MB |
