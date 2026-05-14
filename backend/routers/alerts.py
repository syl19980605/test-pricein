import json

from fastapi import APIRouter

from backend.models.database import get_db

router = APIRouter(tags=["alerts"])


@router.get("/alerts")
async def list_alerts(limit: int = 30):
    db = await get_db()
    cursor = await db.execute(
        "SELECT * FROM alerts ORDER BY created_at DESC LIMIT ?", (limit,)
    )
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        result.append({
            "id": str(r["id"]),
            "symbol": r["symbol"],
            "alert_type": r["alert_type"],
            "severity": r["severity"],
            "title": r["title"],
            "message": r["message"],
            "data": json.loads(r["data"]) if r["data"] else None,
            "created_at": r["created_at"],
            "acknowledged": bool(r["acknowledged"]),
        })
    return result


@router.post("/alerts/{alert_id}/ack")
async def acknowledge_alert(alert_id: int):
    db = await get_db()
    await db.execute("UPDATE alerts SET acknowledged = 1 WHERE id = ?", (alert_id,))
    await db.commit()
    return {"status": "ok"}
