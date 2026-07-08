from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.agents.email_agent import settings as agent_settings
from app.agents.email_agent.service import (
    adjust_item_draft,
    approve_and_send_item,
    discard_item,
    generate_draft_for_item,
    get_item_detail,
    get_item_thread,
    list_items,
    scan_for_reply_candidates,
)
from app.agents.scheduler import scheduler_running
from app.db.email_agent import count_active_items, count_priority_items

router = APIRouter(prefix="/email-agent", tags=["email-agent"])


class AdjustDraftRequest(BaseModel):
    message: str = Field(..., min_length=1)


class ApproveDraftRequest(BaseModel):
    draftResponse: str = Field(..., min_length=1)


@router.get("/status")
async def email_agent_status() -> dict:
    return {
        "enabled": agent_settings.ENABLED,
        "scheduler_running": scheduler_running(),
        "scan_interval_minutes": agent_settings.SCAN_INTERVAL_MINUTES,
        "active_count": await count_active_items(),
        "priority_count": await count_priority_items(),
        "max_queue_size": agent_settings.MAX_ACTIVE_QUEUE_SIZE,
    }


@router.get("/items")
async def get_email_agent_items() -> dict:
    return {"items": await list_items()}


@router.get("/items/{item_id}")
async def get_email_agent_item(item_id: str) -> dict:
    try:
        return await get_item_detail(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/items/{item_id}/thread")
async def get_email_agent_thread(item_id: str) -> dict:
    try:
        return await get_item_thread(item_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/items/{item_id}/adjust")
async def adjust_email_draft(item_id: str, body: AdjustDraftRequest) -> dict:
    try:
        return await adjust_item_draft(item_id, body.message.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/items/{item_id}/approve")
async def approve_email_draft(item_id: str, body: ApproveDraftRequest) -> dict:
    try:
        return await approve_and_send_item(item_id, body.draftResponse.strip())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/items/{item_id}/draft")
async def generate_email_draft(item_id: str) -> dict:
    try:
        item = await generate_draft_for_item(item_id)
        return {"item": item.to_api_dict()}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/items/{item_id}/discard")
async def discard_email_item(item_id: str) -> dict:
    try:
        item = await discard_item(item_id)
        return {"status": "discarded", "id": str(item.id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scan")
async def trigger_email_agent_scan() -> dict:
    if not agent_settings.ENABLED:
        raise HTTPException(status_code=503, detail="Email agent is disabled")

    result = await scan_for_reply_candidates()
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("reason", "Scan failed"))
    return result
