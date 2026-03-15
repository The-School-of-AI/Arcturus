import asyncio
import os
import subprocess
import sys
from pathlib import Path

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables early for all services
load_dotenv()
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Load .env before anything else so env vars are available to all modules.
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / ".env")

# Add project root to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager

from config.settings_loader import reload_settings, reset_settings, save_settings, settings
from core.graph_adapter import nx_to_reactflow
from core.loop import AgentLoop4
from core.persistence import persistence_manager
from core.scheduler import scheduler_service
from memory.context import ExecutionContextManager
from remme.utils import get_embedding
from config.settings_loader import (
    settings,
    save_settings,
    reset_settings,
    reload_settings,
)
from routers.remme import background_smart_scan  # Needed for lifespan startup

# Import shared state
from shared.state import (
    PROJECT_ROOT,
    active_loops,
    get_multi_mcp,
    get_remme_extractor,
    get_remme_store,
)
from routers.remme import background_smart_scan  # Needed for lifespan startup
from routers.sync import run_sync_background  # Phase 4: startup sync when enabled

from contextlib import asynccontextmanager

# Get shared instances
multi_mcp = get_multi_mcp()
remme_store = get_remme_store()
remme_extractor = get_remme_extractor()


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 API Starting up...")

    # 1. Initialize Voice Pipeline FIRST (Zero Cold-Start)
    from voice.orchestrator import Orchestrator
    from voice.voice_wake_service import VoiceWakeService
    from voice.stt_service import STTService
    from voice.deepgram_stt_service import DeepgramSTTService
    from voice.agent import Agent
    from voice.tts_service import TTSService
    from voice.config import VOICE_CONFIG

    try:
        # Create essential services
        voice_agent = Agent()

        # Choose TTS backend based on config
        tts_provider = VOICE_CONFIG.get("tts_provider", "azure")
        if tts_provider == "piper":
            from voice.piper_tts_service import PiperTTSService

            piper_cfg = VOICE_CONFIG.get("piper_tts", {})
            voice_tts = PiperTTSService(
                model_path=piper_cfg.get("model_path"),
                length_scale=piper_cfg.get("length_scale", 1.0),
                sentence_silence=piper_cfg.get("sentence_silence", 0.15),
                speaker_id=piper_cfg.get("speaker_id"),
            )
            print(
                f"🔊 [Voice] TTS provider: Piper (local, streaming={piper_cfg.get('streaming_enabled', False)})"
            )
        else:
            tts_cfg = VOICE_CONFIG.get("tts", {})
            voice_tts = TTSService(
                voice_name=tts_cfg.get("voice_name"),
                personas=tts_cfg.get("personas"),
                active_persona=tts_cfg.get("active_persona"),
            )
            print(f"🔊 [Voice] TTS provider: Azure Speech")

        orchestrator = Orchestrator(
            wake_service=None, stt_service=None, agent=voice_agent, tts=voice_tts
        )

        stt_cfg = VOICE_CONFIG.get("stt", {})
        stt_provider = VOICE_CONFIG.get("stt_provider", "deepgram")
        sample_rate = stt_cfg.get("sample_rate", 16000)
        noise_reduce = stt_cfg.get("noise_reduce", True)

        if stt_provider == "deepgram":
            dg_cfg = stt_cfg.get("deepgram", {})
            voice_stt = DeepgramSTTService(
                sample_rate=sample_rate,
                on_text_callback=orchestrator.on_text,
                language=dg_cfg.get("language", "en"),
                noise_reduce=noise_reduce,
            )
        else:
            w_cfg = stt_cfg.get("whisper", {})
            voice_stt = STTService(
                sample_rate=sample_rate,
                on_text_callback=orchestrator.on_text,
                model_size=w_cfg.get("model_size", "small"),
                device=w_cfg.get("device", "cpu"),
                noise_reduce=noise_reduce,
            )

        voice_wake = VoiceWakeService(on_wake_callback=orchestrator.on_wake)
        orchestrator.wake = voice_wake
        orchestrator.stt = voice_stt
        voice_wake.orchestrator = orchestrator

        voice_wake.start()
        voice_stt.start()
        
        # ── Inject the running event loop so bg threads can publish events ──
        # asyncio.get_event_loop() inside an async context returns the correct
        # running loop. The orchestrator stores this and uses it in _publish()
        # to safely call run_coroutine_threadsafe from wake/STT threads.
        orchestrator._event_loop = asyncio.get_event_loop()
        app.state.orchestrator = orchestrator
        print(f"✅ [Voice] Pipeline WARM and listening (Provider: {stt_provider})")

    except Exception as e:
        print(f"⚠️ [Voice] Startup failed: {e}")

    # 2. Bootstrap & Validate Registry (Slower metadata checks)
    from core.bootstrap import bootstrap_agents
    from core.registry import registry

    try:
        bootstrap_agents()
        registry.validate()
    except Exception as e:
        print(f"❌ Registry Validation Failed: {e}")

    scheduler_service.initialize()
    persistence_manager.load_snapshot()
    # ========== WATCHTOWER: OpenTelemetry bootstrap ==========
    # Initializes tracing and exports spans to MongoDB + Jaeger.
    # FastAPIInstrumentor auto-creates an HTTP span for every request.
    # =========================================================
    watchtower = settings.get("watchtower", {})
    if watchtower.get("enabled", True):
        try:
            from ops.tracing import init_tracing

            init_tracing(
                mongodb_uri=watchtower.get("mongodb_uri", "mongodb://localhost:27017"),
                jaeger_endpoint=watchtower.get("jaeger_endpoint"),
                service_name=watchtower.get("service_name", "arcturus"),
            )
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

            FastAPIInstrumentor.instrument_app(app)
            print("✅ [Watchtower] Tracing initialized")
        except Exception as e:
            print(f"⚠️ [Watchtower] Tracing unavailable (MongoDB not running?): {e}")

    # ========== WATCHTOWER: Periodic Health Checks ==========
    health_scheduler = None
    health_mongo_client = None
    if watchtower.get("enabled", True):
        try:
            from pymongo import MongoClient
            from ops.health.repository import HealthRepository
            from ops.health.scheduler import HealthScheduler
            from ops.health.alerts import AlertEvaluator

            mongo_uri = watchtower.get("mongodb_uri", "mongodb://localhost:27017")
            health_mongo_client = MongoClient(mongo_uri)
            health_coll = health_mongo_client["watchtower"]["health_checks"]
            health_repo = HealthRepository(health_coll)
            alert_evaluator = AlertEvaluator.from_config(watchtower.get("alert_rules", []))
            health_scheduler = HealthScheduler(repository=health_repo, alert_evaluator=alert_evaluator)
            await health_scheduler.start()
            print("✅ [Watchtower] Health scheduler started")
        except Exception as e:
            print(f"⚠️ [Watchtower] Health scheduler unavailable: {e}")

    await multi_mcp.start()

    # 3. External Dependency Checks (Non-blocking or deferred)
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        print("✅ Git found.")
    except Exception:
        print("⚠️ Git NOT found.")

    try:
        import requests  # type: ignore[import-untyped]

        from config.settings_loader import get_ollama_url

        requests.get(get_ollama_url("base"), timeout=1)
        print("✅ Ollama found.")
    except Exception:
        print("⚠️ Ollama NOT found.")
    # 🧠 Start Smart Sync in background
    asyncio.create_task(background_smart_scan())

    # 4. Initialize Nexus gateway adapters (creates httpx clients, Telegram polling, etc.)
    try:
        from shared.state import initialize_message_bus
        await initialize_message_bus()
    except Exception as e:
        print(f"⚠️ [Nexus] Message bus initialization failed: {e}")

    # Phase 4: run sync (push then pull) on startup when SYNC_ENGINE_ENABLED + SYNC_SERVER_URL
    asyncio.create_task(run_sync_background())

    yield

    print("🛑 API Shutting down...")
    if health_scheduler is not None:
        await health_scheduler.stop()
        print("🛑 [Watchtower] Health scheduler stopped")
    if health_mongo_client is not None:
        health_mongo_client.close()
    from ops.tracing import shutdown_tracing

    shutdown_tracing()
    from shared.state import get_canvas_runtime

    get_canvas_runtime().save_snapshots()
    persistence_manager.save_snapshot()
    await multi_mcp.stop()
    # Stop the voice pipeline explicitly so native audio threads don't
    # block process exit (Porcupine's C thread holds the event loop otherwise)
    try:
        if hasattr(app.state, "orchestrator"):
            orch = app.state.orchestrator
            # Cleanly finalise any active dictation session so the file is saved
            if getattr(orch, 'state', None) == 'DICTATING':
                try:
                    orch.stop_dictation()
                    print("✅ [Voice] Dictation session finalised on shutdown.")
                except Exception as de:
                    print(f"⚠️ [Voice] Dictation stop on shutdown failed: {de}")
            orch._cancel_all()
            if orch.wake:
                orch.wake.stop()  # kills Porcupine native thread + PortAudio stream
            if orch.stt:
                orch.stt.stop()  # closes Deepgram/Whisper connection
    except Exception as e:
        print(f"⚠️ [Voice] Shutdown error: {e}")


app = FastAPI(lifespan=lifespan)

# Inject AuthMiddleware for Phase 5 Authentication (JWT/Guest isolation)
from core.auth.middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)

# Enable CORS for Frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "app://.",
    ],  # Explicitly allow frontend
    allow_origin_regex=r"http://localhost:(517\d|5555)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State is now managed in shared/state.py
# active_loops, multi_mcp, remme_store, remme_extractor are imported from there

# === Import and Include Routers ===
from routers import apps as apps_router
from routers import explorer as explorer_router
from routers import mcp as mcp_router
from routers import rag as rag_router
from routers import remme as remme_router
from routers import graph as graph_router
from routers import runs as runs_router
from routers import settings as settings_router
from routers import explorer as explorer_router
from routers import mcp as mcp_router

app.include_router(runs_router.router, prefix="/api")
app.include_router(rag_router.router, prefix="/api")
app.include_router(remme_router.router, prefix="/api")
app.include_router(graph_router.router, prefix="/api")
from routers import sync as sync_router
app.include_router(sync_router.router, prefix="/api")
app.include_router(apps_router.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")
app.include_router(explorer_router.router, prefix="/api")
app.include_router(mcp_router.router, prefix="/api")

# Phase 5: Authentication endpoints
from routers import auth as auth_router
app.include_router(auth_router.router, prefix="/api")

from routers import git as git_router
from routers import news as news_router
from routers import prompts as prompts_router
from routers import news as news_router
from routers import git as git_router

app.include_router(prompts_router.router, prefix="/api")
app.include_router(news_router.router, prefix="/api")
app.include_router(git_router.router, prefix="/api")
from routers import swarm as swarm_router

app.include_router(swarm_router.router, prefix="/api/swarm")


from routers import chat as chat_router

app.include_router(chat_router.router, prefix="/api")
from routers import agent as agent_router

app.include_router(agent_router.router, prefix="/api")
from routers import ide_agent as ide_agent_router

app.include_router(ide_agent_router.router, prefix="/api")
from routers import metrics as metrics_router

app.include_router(metrics_router.router, prefix="/api")
from routers import python_tools

app.include_router(python_tools.router, prefix="/api")
from routers import tests as tests_router

app.include_router(tests_router.router, prefix="/api")
# Chat router included
from routers import inbox

app.include_router(inbox.router, prefix="/api")
from routers import cron

app.include_router(cron.router, prefix="/api")
from routers import stream

app.include_router(stream.router, prefix="/api")
from routers import skills

app.include_router(skills.router, prefix="/api")
from routers import canvas as canvas_router

app.include_router(canvas_router.router, prefix="/api")
from routers import optimizer

app.include_router(optimizer.router, prefix="/api")
from routers import nexus as nexus_router

app.include_router(nexus_router.router, prefix="/api")
from routers import studio as studio_router
from routers import admin as admin_router

app.include_router(studio_router.router, prefix="/api")
app.include_router(admin_router.router, prefix="/api")
from routers.marketplace import router as marketplace_router

app.include_router(marketplace_router, prefix="/api/v3")
from routers import voice as voice_router

app.include_router(voice_router.router, prefix="/api")


from routers import pages as pages_router

app.include_router(pages_router.router, prefix="/api")

# Gateway API v1 (P15)
from gateway_api.v1 import router as gateway_v1_router

app.include_router(gateway_v1_router.router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "1.0.0",
        "mcp_ready": True,  # Since lifespan finishes multi_mcp.start()
    }


if __name__ == "__main__":
    import uvicorn

    # Enable reload=True for development if needed, but here we'll just keep it simple
    # or actually enable it to avoid these restart issues.
    uvicorn.run("api:app", host="0.0.0.0", port=8000, reload=True)
