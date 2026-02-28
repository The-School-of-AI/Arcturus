from fastapi import APIRouter

from gateway_api.v1 import (
    agents,
    chat,
    cron,
    embeddings,
    keys,
    memory,
    pages,
    search,
    studio,
    usage,
    webhooks,
)

router = APIRouter(prefix="/api/v1")
router.include_router(search.router)
router.include_router(chat.router)
router.include_router(embeddings.router)
router.include_router(memory.router)
router.include_router(agents.router)
router.include_router(cron.router)
router.include_router(keys.router)
router.include_router(usage.router)
router.include_router(webhooks.router)
router.include_router(pages.router)
router.include_router(studio.router)
