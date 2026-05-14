"""后台监控：周期性检查头部资产的价格异动、指标穿越、持仓止盈止损，
并刷新到期的用户自建监控。"""
import json
import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.config import MONITOR_INTERVAL
from backend.models.database import get_db
from backend.services.market_data import market_data_service, ASSET_REGISTRY
from backend.services.technical import technical_service

logger = logging.getLogger("bobby.monitor")

scheduler = AsyncIOScheduler()

# 价格异动阈值
PRICE_MOVE_THRESHOLD = 3.0  # 单日 ±3%


async def _create_alert(symbol, alert_type, severity, title, message, data=None):
    db = await get_db()
    await db.execute(
        """INSERT INTO alerts (symbol, alert_type, severity, title, message, data)
        VALUES (?, ?, ?, ?, ?, ?)""",
        (symbol, alert_type, severity, title, message,
         json.dumps(data, ensure_ascii=False) if data else None),
    )
    await db.commit()


async def _check_price_moves():
    """检查显著价格异动。"""
    for symbol in ASSET_REGISTRY:
        try:
            data = await market_data_service.get_current_price(symbol)
            change = data["change_24h_pct"]
            if abs(change) >= PRICE_MOVE_THRESHOLD:
                name = ASSET_REGISTRY[symbol]["name"]
                direction = "上涨" if change > 0 else "下跌"
                severity = "warning" if abs(change) >= 5 else "info"
                await _create_alert(
                    symbol, "price_move", severity,
                    f"{name} 显著{direction} {abs(change):.1f}%",
                    f"{name}({symbol}) 24小时{direction} {abs(change):.2f}%，当前价格 {data['current_price']}。建议复核持仓与消息面是否一致。",
                    {"change_pct": change, "price": data["current_price"]},
                )
        except Exception as e:
            logger.warning(f"price check failed for {symbol}: {e}")


async def _check_indicator_crosses():
    """检查 RSI 进入超买/超卖区。"""
    for symbol in ASSET_REGISTRY:
        try:
            ind = await technical_service.calculate_all(symbol)
            if ind.rsi_14 is None:
                continue
            name = ASSET_REGISTRY[symbol]["name"]
            if ind.rsi_14 >= 75:
                await _create_alert(
                    symbol, "indicator_cross", "warning",
                    f"{name} RSI 超买 ({ind.rsi_14:.0f})",
                    f"{name}({symbol}) RSI 已达 {ind.rsi_14:.1f}，进入超买区。若持有多头，考虑分批止盈。",
                    {"rsi": ind.rsi_14},
                )
            elif ind.rsi_14 <= 25:
                await _create_alert(
                    symbol, "indicator_cross", "info",
                    f"{name} RSI 超卖 ({ind.rsi_14:.0f})",
                    f"{name}({symbol}) RSI 已达 {ind.rsi_14:.1f}，进入超卖区。可关注是否出现中长线买点。",
                    {"rsi": ind.rsi_14},
                )
        except Exception as e:
            logger.warning(f"indicator check failed for {symbol}: {e}")


async def _check_positions():
    """检查持仓是否触及止盈止损。"""
    db = await get_db()
    cursor = await db.execute("SELECT * FROM positions WHERE status = 'open'")
    rows = await cursor.fetchall()
    for row in rows:
        try:
            data = await market_data_service.get_current_price(row["symbol"])
            price = data["current_price"]
            await db.execute(
                "UPDATE positions SET current_price = ? WHERE id = ?", (price, row["id"])
            )

            sl, tp = row["stop_loss"], row["take_profit"]
            direction = row["direction"]
            name = ASSET_REGISTRY.get(row["symbol"], {}).get("name", row["symbol"])

            hit_sl = sl is not None and (
                (direction == "long" and price <= sl) or
                (direction == "short" and price >= sl)
            )
            hit_tp = tp is not None and (
                (direction == "long" and price >= tp) or
                (direction == "short" and price <= tp)
            )

            if hit_sl:
                await db.execute(
                    "UPDATE positions SET status = 'closed_sl', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["id"],),
                )
                await _create_alert(
                    row["symbol"], "stop_loss", "critical",
                    f"{name} 触发止损平仓",
                    f"{name} 价格 {price} 触及止损位 {sl}，已按纪律自动平仓。",
                    {"price": price, "stop_loss": sl},
                )
            elif hit_tp:
                await db.execute(
                    "UPDATE positions SET status = 'closed_tp', closed_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (row["id"],),
                )
                await _create_alert(
                    row["symbol"], "take_profit", "info",
                    f"{name} 触发止盈平仓",
                    f"{name} 价格 {price} 触及止盈位 {tp}，已按纪律自动平仓锁定收益。",
                    {"price": price, "take_profit": tp},
                )
        except Exception as e:
            logger.warning(f"position check failed for {row['symbol']}: {e}")
    await db.commit()


async def _refresh_due_monitors():
    """刷新到期的用户自建监控（按各自的 refresh_interval_min）。"""
    db = await get_db()
    cursor = await db.execute(
        "SELECT id, symbol, refresh_interval_min, last_refreshed_at FROM monitors WHERE status = 'active'"
    )
    rows = await cursor.fetchall()
    now = datetime.now(timezone.utc)
    for row in rows:
        try:
            last_str = (row["last_refreshed_at"] or "").replace(" ", "T")
            last_dt = datetime.fromisoformat(last_str) if last_str else None
            if last_dt is not None and last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            due = last_dt is None or (
                (now - last_dt).total_seconds() >= row["refresh_interval_min"] * 60
            )
            if due:
                from backend.services.monitor_service import monitor_service
                await monitor_service.refresh_monitor(row["id"])
                logger.info(f"Refreshed monitor {row['id']} ({row['symbol']})")
        except Exception as e:
            logger.warning(f"monitor refresh failed for {row['id']}: {e}")


async def run_monitor_cycle():
    logger.info("Running monitor cycle...")
    await _check_price_moves()
    await _check_indicator_crosses()
    await _check_positions()
    await _refresh_due_monitors()


def start_scheduler():
    scheduler.add_job(
        run_monitor_cycle,
        "interval",
        seconds=MONITOR_INTERVAL,
        id="monitor_cycle",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(f"Monitor scheduler started (interval={MONITOR_INTERVAL}s)")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
