from fastapi import APIRouter
from app.services.prompts import (
    DEHYDRATE_SYSTEM, DEHYDRATE_USER,
    POSITION_HINT_EARLY, POSITION_HINT_NORMAL,
)

router = APIRouter(prefix="/api", tags=["prompts"])


@router.get("/prompts/defaults")
async def get_prompt_defaults():
    """Return all built-in default prompt templates (for display in settings UI)."""
    return {
        "system": DEHYDRATE_SYSTEM,
        "user": DEHYDRATE_USER,
        "position_early": POSITION_HINT_EARLY,
        "position_normal": POSITION_HINT_NORMAL,
    }
