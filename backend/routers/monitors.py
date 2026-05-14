from fastapi import APIRouter, HTTPException

from backend.services.monitor_service import monitor_service

router = APIRouter(tags=["monitors"])


@router.get("/monitors")
async def list_monitors():
    monitors = await monitor_service.list_monitors()
    return [m.model_dump(mode="json") for m in monitors]


@router.get("/monitors/{monitor_id}")
async def get_monitor(monitor_id: int):
    try:
        m = await monitor_service.get_monitor(monitor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return m.model_dump(mode="json")


@router.post("/monitors/{monitor_id}/refresh")
async def refresh_monitor(monitor_id: int):
    try:
        m = await monitor_service.refresh_monitor(monitor_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    return m.model_dump(mode="json")


@router.delete("/monitors/{monitor_id}")
async def delete_monitor(monitor_id: int):
    from backend.models.database import get_db
    db = await get_db()
    await db.execute("UPDATE monitors SET status = 'archived' WHERE id = ?", (monitor_id,))
    await db.commit()
    return {"status": "ok"}
