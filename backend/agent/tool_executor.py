"""Executes Bobby's tool calls by delegating to backend services."""
import asyncio
import json

from backend.models.database import get_db
from backend.services.market_data import market_data_service, ASSET_REGISTRY
from backend.services.technical import technical_service
from backend.services.news_service import news_service
from backend.services.signal_engine import signal_engine
from backend.services.news_impact import news_impact_analyzer
from backend.services.prediction_market import prediction_market_service
from backend.services.monitor_service import monitor_service
from backend.agent.strategy_gen import strategy_generator


async def execute_tool(name: str, args: dict) -> dict:
    """Returns {"result": <data>, "cards": [<optional structured cards for UI>]}."""
    try:
        if name == "get_asset_price":
            symbol = args["symbol"]
            data = await market_data_service.get_current_price(symbol)
            meta = ASSET_REGISTRY.get(symbol, {})
            return {"result": {"symbol": symbol, "name": meta.get("name", symbol), **data}}

        if name == "get_technical_indicators":
            symbol = args["symbol"]
            ind = await technical_service.calculate_all(symbol)
            return {"result": ind.model_dump(mode="json")}

        if name == "analyze_news_sentiment":
            symbol = args["symbol"]
            news = await news_service.get_news(symbol)
            return {
                "result": {
                    "symbol": symbol,
                    "news_count": len(news),
                    "headlines": [
                        {"title": n.title, "source": n.source,
                         "published_at": n.published_at.isoformat()}
                        for n in news[:8]
                    ],
                }
            }

        if name == "generate_strategy_card":
            symbols = args["symbols"]
            risk = args.get("risk_level", "moderate")
            card = await strategy_generator.generate(symbols, risk)
            return {
                "result": card.model_dump(mode="json"),
                "cards": [{"type": "strategy", "data": card.model_dump(mode="json")}],
            }

        if name == "begin_analysis":
            return await _begin_analysis(args)

        if name == "analyze_asset":
            return await _analyze_asset(args)

        if name == "create_monitor":
            return await _create_monitor(args)

        if name == "manage_position":
            return await _manage_position(args)

        return {"result": {"error": f"未知工具: {name}"}}

    except Exception as e:
        return {"result": {"error": f"工具 {name} 执行失败: {str(e)}"}}


# ── 统一分析流程：horizon-first ──

_HORIZON_LABEL = {"short": "短期", "mid": "中长线", "long": "长期"}


async def _begin_analysis(args: dict) -> dict:
    """统一流程第一步：只问持有期。持有期是整条分析的前置参数。
    选项带结构化 action —— 点击后后端直接执行 analyze_asset。
    news_event / user_hypothesis 可选 —— 用户提到了才带上。"""
    symbol = args["symbol"]
    news_event = args.get("news_event") or ""
    user_hypothesis = args.get("user_hypothesis") or ""
    name = ASSET_REGISTRY.get(symbol, {}).get("name", symbol)

    def _opt(label: str, horizon: str):
        action_args = {"symbol": symbol, "horizon": horizon}
        if news_event:
            action_args["news_event"] = news_event
        if user_hypothesis:
            action_args["user_hypothesis"] = user_hypothesis
        return {
            "label": label,
            "message": f"我对 {name} 的持有期是{label}，按这个做完整分析",
            "variant": "primary",
            "action": {"tool": "analyze_asset", "args": action_args},
        }

    ask = {
        "type": "ask",
        "data": {
            "question": (
                f"在分析 {name} 之前，先确认你对它的**持有期预期** —— "
                f"投资预期是定价分析的前置参数：「定价程度」是 horizon-conditional 的，"
                f"短/中/长线看到的是不同时间维度的定价。"
            ),
            "options": [
                _opt("短期（数天-数周）", "short"),
                _opt("中长线（数月）", "mid"),
                _opt("长期（一年以上）", "long"),
            ],
        },
    }
    return {
        "result": {"symbol": symbol, "stage": "awaiting_horizon", "news_event": news_event},
        "cards": [ask],
    }


async def _analyze_asset(args: dict) -> dict:
    """统一分析流程核心：编排 预测市场篮子 + 综合信号 +（可选）消息影响，
    给出买卖结论。自适应卡片：泛问出 信号卡+预测市场卡；提到消息再加 消息影响卡。"""
    symbol = args["symbol"]
    horizon = args.get("horizon", "mid")
    news_event = args.get("news_event") or ""
    user_hypothesis = args.get("user_hypothesis") or ""
    name = ASSET_REGISTRY.get(symbol, {}).get("name", symbol)

    # 三个分析互相独立 —— 并行执行（之前串行导致带消息时要 200s+）
    event_desc = news_event or f"{name} 当前的整体价格驱动因素与市场关注点"
    tasks = [
        prediction_market_service.find_basket(symbol, event_desc, horizon),  # 预测市场篮子
        signal_engine.generate_signal(symbol),                               # 综合信号
    ]
    if news_event:
        tasks.append(news_impact_analyzer.analyze(
            symbol, news_event, user_hypothesis or None, horizon
        ))
    results = await asyncio.gather(*tasks)
    pm_basket = results[0]
    signal = results[1]
    news_result = results[2] if news_event else None

    # PM 篮子融入信号的 priced_in（编排器后处理，让上面三个分析能并行）
    if pm_basket.matched:
        signal.priced_in_score = round(
            signal.priced_in_score * 0.5 + pm_basket.aggregate_priced_in * 0.5, 3
        )
        signal.key_factors = signal.key_factors + [
            f"预测市场篮子: {len(pm_basket.items)}个市场, 聚合定价度{round(pm_basket.aggregate_priced_in * 100)}%"
        ]
    await _save_signal(signal)

    # 自适应卡片：信号卡 + 预测市场卡 +（有消息才）消息影响卡 + ask
    cards = [
        {"type": "signal", "data": signal.model_dump(mode="json")},
        {"type": "prediction_market", "data": pm_basket.model_dump(mode="json")},
    ]
    if news_result is not None:
        cards.append({"type": "news_impact", "data": news_result.model_dump(mode="json")})

    # 监控方向：有消息分析就用它判定的方向，否则用信号方向
    if news_result is not None:
        direction = news_result.user_direction or "bullish"
    else:
        direction = "bullish" if signal.direction.value in ("strong_buy", "buy") else (
            "bearish" if signal.direction.value in ("strong_sell", "sell") else "bullish"
        )
    thesis = news_event or f"对 {name} 的{_HORIZON_LABEL.get(horizon, horizon)}持有分析"

    def _mon_opt(label: str, interval: int, variant: str):
        return {
            "label": label,
            "message": f"帮我为 {name} 创建监控（{label}）",
            "variant": variant,
            "action": {
                "tool": "create_monitor",
                "args": {
                    "symbol": symbol, "thesis": thesis, "direction": direction,
                    "horizon": horizon, "refresh_interval_min": interval,
                },
            },
        }

    cards.append({
        "type": "ask",
        "data": {
            "question": f"是否为 {name} 创建持续监控？我会按你的「{_HORIZON_LABEL.get(horizon, horizon)}」持有期，定期刷新它的价格影响消息、信号和定价程度。",
            "options": [
                _mon_opt("创建 · 每小时刷新", 60, "primary"),
                _mon_opt("创建 · 每4小时", 240, "default"),
                _mon_opt("创建 · 每天", 1440, "default"),
                {"label": "暂不创建", "message": "暂时不创建监控", "variant": "default"},
            ],
        },
    })
    return {
        "result": {
            "symbol": symbol, "horizon": horizon,
            "signal": signal.model_dump(mode="json"),
            "prediction_market": pm_basket.model_dump(mode="json"),
            "news_impact": news_result.model_dump(mode="json") if news_result else None,
        },
        "cards": cards,
    }


async def _create_monitor(args: dict) -> dict:
    symbol = args["symbol"]
    thesis = args.get("thesis", "")
    direction = args.get("direction", "bullish")
    horizon = args.get("horizon", "mid")
    interval = int(args.get("refresh_interval_min", 60))
    monitor = await monitor_service.create_monitor(symbol, thesis, direction, horizon, interval)
    data = monitor.model_dump(mode="json")
    name = monitor.name

    # ask：是否直接挂单。选项带结构化 action —— 点击后后端直接执行 manage_position。
    def _trade_opt(label: str, trade_dir: str, variant: str):
        return {
            "label": label,
            "message": f"基于这个分析帮我{label} {name}，1股，止损8% 止盈20%",
            "variant": variant,
            "action": {
                "tool": "manage_position",
                "args": {
                    "action": "open",
                    "symbol": symbol,
                    "direction": trade_dir,
                    "quantity": 1,
                    "stop_loss_pct": 8,
                    "take_profit_pct": 20,
                },
            },
        }

    ask = {
        "type": "ask",
        "data": {
            "question": f"监控已创建。基于以上分析，是否直接为你挂单？（模拟交易）",
            "options": [
                _trade_opt("挂单做多", "long", "primary"),
                _trade_opt("挂单做空", "short", "default"),
                {"label": "我再想想", "message": "我再想想，暂不挂单", "variant": "default"},
            ],
        },
    }
    return {
        "result": data,
        "cards": [{"type": "monitor", "data": data}, ask],
    }


# ── 持久化 / 持仓 ──

async def _save_signal(signal):
    db = await get_db()
    await db.execute(
        """INSERT INTO signals
        (symbol, direction, confidence, technical_score, sentiment_score,
         priced_in_score, reasoning, key_factors)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            signal.symbol, signal.direction.value, signal.confidence,
            signal.technical_score, signal.sentiment_score, signal.priced_in_score,
            signal.reasoning, json.dumps(signal.key_factors, ensure_ascii=False),
        ),
    )
    await db.commit()


async def _manage_position(args: dict) -> dict:
    action = args["action"]
    db = await get_db()

    if action == "list":
        cursor = await db.execute(
            "SELECT * FROM positions WHERE status = 'open' ORDER BY opened_at DESC"
        )
        rows = await cursor.fetchall()
        return {"result": {"positions": [dict(r) for r in rows]}}

    if action == "open":
        symbol = args["symbol"]
        direction = args.get("direction", "long")
        quantity = args.get("quantity", 1.0)
        price_data = await market_data_service.get_current_price(symbol)
        entry = price_data["current_price"]

        stop_loss = None
        take_profit = None
        if args.get("stop_loss_pct"):
            pct = args["stop_loss_pct"] / 100
            stop_loss = round(entry * (1 - pct) if direction == "long" else entry * (1 + pct), 2)
        if args.get("take_profit_pct"):
            pct = args["take_profit_pct"] / 100
            take_profit = round(entry * (1 + pct) if direction == "long" else entry * (1 - pct), 2)

        cursor = await db.execute(
            """INSERT INTO positions
            (symbol, direction, entry_price, current_price, quantity, stop_loss, take_profit, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'open')""",
            (symbol, direction, entry, entry, quantity, stop_loss, take_profit),
        )
        await db.commit()
        return {
            "result": {
                "id": cursor.lastrowid, "symbol": symbol, "direction": direction,
                "entry_price": entry, "quantity": quantity,
                "stop_loss": stop_loss, "take_profit": take_profit, "status": "open",
            }
        }

    if action == "close":
        symbol = args["symbol"]
        cursor = await db.execute(
            "SELECT * FROM positions WHERE symbol = ? AND status = 'open' ORDER BY opened_at DESC LIMIT 1",
            (symbol,),
        )
        row = await cursor.fetchone()
        if not row:
            return {"result": {"error": f"没有找到 {symbol} 的持仓"}}
        price_data = await market_data_service.get_current_price(symbol)
        exit_price = price_data["current_price"]
        await db.execute(
            "UPDATE positions SET status = 'closed_manual', current_price = ?, closed_at = CURRENT_TIMESTAMP WHERE id = ?",
            (exit_price, row["id"]),
        )
        await db.commit()
        entry = row["entry_price"]
        pnl_pct = round((exit_price - entry) / entry * 100, 2)
        if row["direction"] == "short":
            pnl_pct = -pnl_pct
        return {
            "result": {
                "id": row["id"], "symbol": symbol, "entry_price": entry,
                "exit_price": exit_price, "pnl_pct": pnl_pct, "status": "closed",
            }
        }

    return {"result": {"error": f"未知操作: {action}"}}
