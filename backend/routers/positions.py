from fastapi import APIRouter

from backend.models.database import get_db
from backend.models.schemas import PositionCreate
from backend.services.market_data import market_data_service, ASSET_REGISTRY

router = APIRouter(tags=["positions"])


def _compute_pnl(row, current_price: float) -> dict:
    entry = row["entry_price"]
    qty = row["quantity"]
    if row["direction"] == "long":
        pnl = (current_price - entry) * qty
    else:
        pnl = (entry - current_price) * qty
    pnl_pct = (pnl / (entry * qty) * 100) if entry and qty else 0.0
    return {"pnl": round(pnl, 2), "pnl_pct": round(pnl_pct, 2)}


@router.get("/positions")
async def list_positions():
    db = await get_db()
    cursor = await db.execute("SELECT * FROM positions ORDER BY opened_at DESC")
    rows = await cursor.fetchall()
    result = []
    for r in rows:
        current_price = r["current_price"] or r["entry_price"]
        if r["status"] == "open":
            try:
                data = await market_data_service.get_current_price(r["symbol"])
                current_price = data["current_price"]
            except Exception:
                pass
        pnl = _compute_pnl(r, current_price)
        result.append({
            "id": str(r["id"]),
            "symbol": r["symbol"],
            "name": ASSET_REGISTRY.get(r["symbol"], {}).get("name", r["symbol"]),
            "direction": r["direction"],
            "entry_price": r["entry_price"],
            "current_price": current_price,
            "quantity": r["quantity"],
            "stop_loss": r["stop_loss"],
            "take_profit": r["take_profit"],
            "status": r["status"],
            "opened_at": r["opened_at"],
            **pnl,
        })
    return result


@router.post("/positions")
async def create_position(req: PositionCreate):
    db = await get_db()
    data = await market_data_service.get_current_price(req.symbol)
    entry = data["current_price"]

    stop_loss = None
    take_profit = None
    if req.stop_loss_pct:
        pct = req.stop_loss_pct / 100
        stop_loss = round(entry * (1 - pct) if req.direction == "long" else entry * (1 + pct), 2)
    if req.take_profit_pct:
        pct = req.take_profit_pct / 100
        take_profit = round(entry * (1 + pct) if req.direction == "long" else entry * (1 - pct), 2)

    cursor = await db.execute(
        """INSERT INTO positions
        (symbol, direction, entry_price, current_price, quantity, stop_loss, take_profit, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'open')""",
        (req.symbol, req.direction, entry, entry, req.quantity, stop_loss, take_profit),
    )
    await db.commit()
    return {
        "id": str(cursor.lastrowid),
        "symbol": req.symbol,
        "direction": req.direction,
        "entry_price": entry,
        "quantity": req.quantity,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "status": "open",
    }


@router.put("/positions/{position_id}/close")
async def close_position(position_id: int):
    db = await get_db()
    cursor = await db.execute("SELECT * FROM positions WHERE id = ?", (position_id,))
    row = await cursor.fetchone()
    if not row:
        return {"error": "持仓不存在"}
    data = await market_data_service.get_current_price(row["symbol"])
    exit_price = data["current_price"]
    await db.execute(
        "UPDATE positions SET status = 'closed_manual', current_price = ?, closed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (exit_price, position_id),
    )
    await db.commit()
    pnl = _compute_pnl(row, exit_price)
    return {"id": str(position_id), "exit_price": exit_price, "status": "closed_manual", **pnl}
