import asyncio

from fastapi import APIRouter
from backend.services.market_data import market_data_service, ASSET_REGISTRY
from backend.services.technical import technical_service

router = APIRouter(tags=["assets"])


@router.get("/assets")
async def list_assets():
    assets = await market_data_service.get_all_assets()
    # sparkline 并行拉取（之前是 for 循环里串行 await，11 个资产要 25s+）
    sparklines = await asyncio.gather(
        *[market_data_service.get_sparkline(a.symbol) for a in assets]
    )
    return [
        {**asset.model_dump(), "price_history_7d": sparkline}
        for asset, sparkline in zip(assets, sparklines)
    ]


@router.get("/assets/{symbol}")
async def get_asset(symbol: str):
    if symbol not in ASSET_REGISTRY:
        return {"error": f"Unknown symbol: {symbol}"}
    price_data = await market_data_service.get_current_price(symbol)
    sparkline = await market_data_service.get_sparkline(symbol)
    meta = ASSET_REGISTRY[symbol]
    return {
        "symbol": symbol,
        "name": meta["name"],
        "asset_class": meta["asset_class"],
        **price_data,
        "price_history_7d": sparkline,
    }


@router.get("/assets/{symbol}/indicators")
async def get_asset_indicators(symbol: str):
    indicators = await technical_service.calculate_all(symbol)
    return indicators.model_dump()


@router.get("/assets/{symbol}/history")
async def get_asset_history(symbol: str, period: str = "3mo"):
    df = await market_data_service.get_price_history(symbol, period)
    if df.empty:
        return []
    records = []
    for idx, row in df.iterrows():
        records.append({
            "date": idx.isoformat(),
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
            "volume": float(row["Volume"]),
        })
    return records
