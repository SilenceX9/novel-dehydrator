from fastapi import APIRouter
from pydantic import BaseModel
from app.database import get_db

router = APIRouter(prefix="/api/settings", tags=["settings"])


class SettingsIn(BaseModel):
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"
    concurrency: int = 20
    system_prompt: str = ""


class SettingsOut(SettingsIn):
    pass


@router.get("", response_model=SettingsOut)
async def get_settings():
    async with get_db() as db:
        async with db.execute("SELECT * FROM app_settings WHERE id=1") as cur:
            row = await cur.fetchone()
    if not row:
        return SettingsOut()
    return SettingsOut(
        deepseek_api_key=row["deepseek_api_key"] or "",
        deepseek_model=row["deepseek_model"] or "deepseek-v4-flash",
        deepseek_base_url=row["deepseek_base_url"] or "https://api.deepseek.com",
        concurrency=row["concurrency"] if row["concurrency"] else 5,
        system_prompt=row["system_prompt"] or "",
    )


@router.put("", response_model=SettingsOut)
async def update_settings(data: SettingsIn):
    async with get_db() as db:
        await db.execute(
            """UPDATE app_settings SET
               deepseek_api_key=?, deepseek_model=?, deepseek_base_url=?,
               concurrency=?, system_prompt=?
               WHERE id=1""",
            (data.deepseek_api_key, data.deepseek_model, data.deepseek_base_url,
             data.concurrency, data.system_prompt),
        )
        await db.commit()
    return data
