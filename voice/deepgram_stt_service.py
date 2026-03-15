# voice/deepgram_stt_service.py

"""
Cloud-based STT using Deepgram's Nova-2 model via WebSocket streaming.
Implements the same interface as STTService (push_audio, start, stop, cancel)
so the Orchestrator can use either provider interchangeably.
"""

import os
import threading
import time
import json
import numpy as np

try:
    import noisereduce as nr
    _HAS_NOISEREDUCE = True
except ImportError:
    _HAS_NOISEREDUCE = False

try:
    import websocket  # websocket-client
    _HAS_WEBSOCKET = True
except ImportError:
    _HAS_WEBSOCKET = False
    print("⚠️ [DeepgramSTT] websocket-client not installed. "
          "Install with: pip install websocket-client")


class DeepgramSTTService:
    """
    Streams audio to Deepgram via WebSocket for real-time transcription.
    Uses Deepgram Nova-2 by default for best accuracy.
    """

    DEEPGRAM_WS_URL = (
        "wss://api.deepgram.com/v1/listen"
        "?model=nova-2"
        "&encoding=linear16"
        "&sample_rate={sample_rate}"
        "&channels=1"
        "&punctuate=true"
        "&smart_format=true"
        "&numerals=true"
        "&interim_results=false"
        "&language={language}"
    )

    def __init__(
        self,
        sample_rate: int,
        on_text_callback,
        api_key: str = None,
        language: str = "en",
        noise_reduce: bool = True,
    ):
        self.sample_rate = sample_rate
        self.on_text = on_text_callback
        
        # Sanitize API key: remove any surrounding quotes or spaces from .env
        raw_key = api_key or os.environ.get("DEEPGRAM_API_KEY", "")
        self.api_key = raw_key.strip().strip("'").strip('"')
        
        self.language = language
        self.noise_reduce = noise_reduce and _HAS_NOISEREDUCE

        self._audio_buffer = []
        self._lock = threading.Lock()
        self._running = False
        self._ws = None
        self._send_thread = None
        self._recv_thread = None
        self._frame_counter = 0

        if not self.api_key:
            print("⚠️ [DeepgramSTT] No API key found. Add DEEPGRAM_API_KEY to the project root .env")

        if self.noise_reduce:
            print("✅ [DeepgramSTT] Noise reduction enabled")

    def start(self):
        """Start the background threads. Connection is handled in the send loop."""
        if not _HAS_WEBSOCKET:
            print("❌ [DeepgramSTT] Cannot start — websocket-client not installed.")
            return

        if not self.api_key:
            print("❌ [DeepgramSTT] Cannot start — no DEEPGRAM_API_KEY.")
            return

        self._running = True
        
        # Start loops but don't block on connection here
        self._send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self._recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
        self._send_thread.start()
        self._recv_thread.start()

    def _connect(self):
        """Establish WebSocket connection to Deepgram."""
        url = self.DEEPGRAM_WS_URL.format(
            sample_rate=self.sample_rate,
            language=self.language,
        )
        self._ws = websocket.WebSocket()
        self._ws.connect(url, header=[f"Authorization: Token {self.api_key}"])

    def stop(self):
        """Gracefully close the connection."""
        self._running = False
        time.sleep(0.05)
        self._close_ws()
        self._clear_buffer()

    def cancel(self):
        """Hard cancel: drop buffer immediately."""
        self._clear_buffer()

    def push_audio(self, pcm_frame):
        """
        pcm_frame: tuple[int] or np.int16 array — same contract as STTService.
        """
        with self._lock:
            self._audio_buffer.extend(pcm_frame)

    def _clear_buffer(self):
        with self._lock:
            self._audio_buffer.clear()

    def _denoise(self, audio: np.ndarray) -> np.ndarray:
        """Apply stationary noise reduction, same as local STTService."""
        try:
            return nr.reduce_noise(
                y=audio,
                sr=self.sample_rate,
                stationary=True,
                prop_decrease=0.75,
                n_fft=512,
                n_std_thresh_stationary=1.5,
            )
        except Exception as e:
            print(f"⚠️ [DeepgramSTT] Noise reduction failed: {e}")
            return audio

    def _send_loop(self):
        """
        Continuously drain the audio buffer and send raw PCM bytes
        to Deepgram over the WebSocket.
        """
        last_keep_alive = time.time()
        
        while self._running:
            try:
                # 0. Ensure connected
                if not self._ws or not self._ws.connected:
                    try:
                        self._connect()
                        print("✅ [DeepgramSTT] Streaming connection established.")
                    except Exception as e:
                        time.sleep(2.0)
                        continue

                time.sleep(0.1)  # ~100ms chunks

                with self._lock:
                    if len(self._audio_buffer) < self.sample_rate * 0.1:
                        # Send KeepAlive if we've been idle for > 8 seconds
                        if time.time() - last_keep_alive > 8.0:
                            try:
                                self._ws.send(json.dumps({"type": "KeepAlive"}))
                                last_keep_alive = time.time()
                            except Exception:
                                pass
                        continue
                    
                    pcm = np.array(self._audio_buffer, dtype=np.int16)
                    self._audio_buffer.clear()
                    last_keep_alive = time.time()

                # Optional noise reduction
                if self.noise_reduce:
                    audio_f32 = pcm.astype(np.float32) / 32768.0
                    audio_f32 = self._denoise(audio_f32)
                    pcm = (audio_f32 * 32768.0).astype(np.int16)

                self._ws.send(pcm.tobytes(), opcode=websocket.ABNF.OPCODE_BINARY)

            except Exception as e:
                if self._running:
                    print(f"⚠️ [DeepgramSTT] Send loop error: {e}")
                    self._try_reconnect()
                    time.sleep(1.0)

    def _recv_loop(self):
        """
        Listen for transcription results from Deepgram and forward
        final transcripts to the on_text callback.
        """
        while self._running:
            try:
                if not self._ws or not self._ws.connected:
                    time.sleep(0.5)
                    continue

                raw = self._ws.recv()
                if not raw:
                    continue

                msg = json.loads(raw)

                # Deepgram response structure
                channel = msg.get("channel", {})
                alternatives = channel.get("alternatives", [])
                if not alternatives:
                    continue

                transcript = alternatives[0].get("transcript", "").strip()
                is_final = msg.get("is_final", True)

                if transcript and is_final:
                    self.on_text(transcript)

            except Exception as e:
                if self._running:
                    # WebSocketConnectionClosedException is handled by _send_loop reconnection usually
                    # but we catch it here to prevent thread death
                    time.sleep(0.5)

    def _try_reconnect(self):
        """Attempt to reconnect after a connection drop."""
        with self._lock:
            # Prevent multiple simultaneous reconnect attempts
            if self._ws and self._ws.connected:
                return

            self._close_ws()
            for attempt in range(5):
                try:
                    time.sleep(1.0 * (attempt + 1))
                    self._connect()
                    print(f"✅ [DeepgramSTT] Reconnected (attempt {attempt + 1})")
                    return
                except Exception as e:
                    print(f"⚠️ [DeepgramSTT] Reconnect attempt {attempt + 1} failed: {e}")
            
            print("❌ [DeepgramSTT] Could not reconnect. STT may be offline.")

    def _close_ws(self):
        """Safely close the WebSocket."""
        try:
            if self._ws:
                self._ws.close()
        except Exception:
            pass
        self._ws = None
