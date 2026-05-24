import asyncio
import json
import httpx
from app.config import settings
from app.database import get_db


async def _get_runtime_settings() -> dict:
    """从 DB 读取配置，若未设置则回退到 .env。"""
    try:
        async with get_db() as db:
            async with db.execute("SELECT * FROM app_settings WHERE id=1") as cur:
                row = await cur.fetchone()
        if row and row["deepseek_api_key"]:
            return {
                "api_key": row["deepseek_api_key"],
                "model": row["deepseek_model"] or settings.deepseek_model,
                "base_url": row["deepseek_base_url"] or settings.deepseek_base_url,
            }
    except Exception:
        pass
    return {
        "api_key": settings.deepseek_api_key,
        "model": settings.deepseek_model,
        "base_url": settings.deepseek_base_url,
    }


async def chat_completion(messages: list, stream: bool = True) -> str:
    cfg = await _get_runtime_settings()
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": cfg["model"],
        "messages": messages,
        "stream": stream,
        "temperature": 0.3,
    }

    last_err = None
    for attempt in range(settings.max_retries):
        try:
            async with httpx.AsyncClient(
                base_url=cfg["base_url"],
                timeout=httpx.Timeout(connect=15, read=300, write=30, pool=15),
            ) as client:
                if stream:
                    return await _stream_completion(client, headers, payload)
                else:
                    resp = await client.post("/chat/completions", headers=headers, json=payload)
                    resp.raise_for_status()
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as e:
            last_err = e
            if e.response.status_code == 429:
                await asyncio.sleep(30 * (attempt + 1))
            else:
                await asyncio.sleep(2 ** attempt)
        except Exception as e:
            last_err = e
            await asyncio.sleep(2 ** attempt)

    raise RuntimeError(f"DeepSeek API failed after {settings.max_retries} retries: {last_err}")


async def _stream_completion(client: httpx.AsyncClient, headers: dict, payload: dict) -> str:
    chunks = []
    async with client.stream("POST", "/chat/completions", headers=headers, json=payload) as resp:
        resp.raise_for_status()
        async for line in resp.aiter_lines():
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
                delta = obj["choices"][0]["delta"].get("content", "")
                if delta:
                    chunks.append(delta)
            except Exception:
                continue
    return "".join(chunks)
