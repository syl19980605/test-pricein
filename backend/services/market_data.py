import asyncio
import math
import time
from datetime import datetime
from functools import lru_cache
from typing import Optional

import pandas as pd
import yfinance as yf

from backend.models.schemas import Asset, AssetClass


def _safe_num(v, default=0.0):
    """把 yfinance 偶尔返回的 NaN/inf 清成安全值 —— 否则 FastAPI 序列化 JSON 会报错。"""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return default
    if math.isnan(f) or math.isinf(f):
        return default
    return f

# 注：A股（600519.SS 茅台 / 688256.SS 寒武纪）已移除 —— Yahoo Finance 不向
# 海外云 IP 提供 A 股数据，部署到 Render（新加坡）后拉不到。只保留能稳定取数的标的。
ASSET_REGISTRY = {
    "GC=F":     {"name": "黄金期货", "asset_class": AssetClass.COMMODITY},
    "BTC-USD":  {"name": "比特币", "asset_class": AssetClass.CRYPTO},
    "AAPL":     {"name": "Apple", "asset_class": AssetClass.US_STOCK},
    "MSFT":     {"name": "Microsoft", "asset_class": AssetClass.US_STOCK},
    "GOOGL":    {"name": "Alphabet", "asset_class": AssetClass.US_STOCK},
    "AMZN":     {"name": "Amazon", "asset_class": AssetClass.US_STOCK},
    "NVDA":     {"name": "NVIDIA", "asset_class": AssetClass.US_STOCK},
    "META":     {"name": "Meta", "asset_class": AssetClass.US_STOCK},
    "TSLA":     {"name": "Tesla", "asset_class": AssetClass.US_STOCK},
}

_price_cache: dict[str, tuple[float, dict]] = {}
_sparkline_cache: dict[str, tuple[float, list]] = {}
CACHE_TTL = 30           # 当前价缓存 30s
SPARKLINE_TTL = 300      # 7天迷你图缓存 5min（盘中基本不变，无需频繁重拉）


def _fetch_current(symbol: str) -> dict:
    now = time.time()
    cached = _price_cache.get(symbol)
    if cached and (now - cached[0]) < CACHE_TTL:
        return cached[1]

    ticker = yf.Ticker(symbol)
    hist = ticker.history(period="5d")
    if hist.empty:
        result = {
            "current_price": 0.0,
            "change_24h_pct": 0.0,
            "volume_24h": 0.0,
            "market_cap": None,
        }
        _price_cache[symbol] = (now, result)
        return result

    current_price = _safe_num(hist["Close"].iloc[-1])
    if len(hist) >= 2:
        prev_price = _safe_num(hist["Close"].iloc[-2])
        change_pct = ((current_price - prev_price) / prev_price) * 100 if prev_price else 0.0
    else:
        change_pct = 0.0

    volume = _safe_num(hist["Volume"].iloc[-1]) if "Volume" in hist.columns else 0.0

    # fast_info 比 .info 快一个数量级（.info 会拉取大段 JSON）
    market_cap = None
    try:
        mc = ticker.fast_info.get("marketCap")
        market_cap = _safe_num(mc, default=None) if mc is not None else None
    except Exception:
        pass

    result = {
        "current_price": round(current_price, 2),
        "change_24h_pct": round(_safe_num(change_pct), 2),
        "volume_24h": volume,
        "market_cap": market_cap,
    }
    _price_cache[symbol] = (now, result)
    return result


def _fetch_history(symbol: str, period: str = "1mo") -> pd.DataFrame:
    ticker = yf.Ticker(symbol)
    return ticker.history(period=period)


def _fetch_price_series_7d(symbol: str) -> list[float]:
    now = time.time()
    cached = _sparkline_cache.get(symbol)
    if cached and (now - cached[0]) < SPARKLINE_TTL:
        return cached[1]
    hist = _fetch_history(symbol, period="7d")
    if hist.empty:
        series = []
    else:
        # 过滤掉 NaN/inf 点 —— 否则 sparkline 数组里的坏值会让 JSON 序列化失败
        series = [
            round(_safe_num(p), 2) for p in hist["Close"].tolist()
            if not (isinstance(p, float) and (math.isnan(p) or math.isinf(p)))
        ]
    _sparkline_cache[symbol] = (now, series)
    return series


class MarketDataService:
    def __init__(self):
        self._loop = None

    def _get_loop(self):
        if self._loop is None:
            self._loop = asyncio.get_event_loop()
        return self._loop

    async def get_current_price(self, symbol: str) -> dict:
        return await asyncio.get_event_loop().run_in_executor(None, _fetch_current, symbol)

    async def get_all_assets(self) -> list[Asset]:
        tasks = []
        for symbol in ASSET_REGISTRY:
            tasks.append(self._build_asset(symbol))
        return await asyncio.gather(*tasks)

    async def _build_asset(self, symbol: str) -> Asset:
        meta = ASSET_REGISTRY[symbol]
        price_data = await self.get_current_price(symbol)
        return Asset(
            symbol=symbol,
            name=meta["name"],
            asset_class=meta["asset_class"],
            current_price=price_data["current_price"],
            change_24h_pct=price_data["change_24h_pct"],
            volume_24h=price_data["volume_24h"],
            market_cap=price_data["market_cap"],
            last_updated=datetime.utcnow(),
        )

    async def get_price_history(self, symbol: str, period: str = "3mo") -> pd.DataFrame:
        return await asyncio.get_event_loop().run_in_executor(
            None, _fetch_history, symbol, period
        )

    async def get_sparkline(self, symbol: str) -> list[float]:
        return await asyncio.get_event_loop().run_in_executor(
            None, _fetch_price_series_7d, symbol
        )

    async def get_news(self, symbol: str) -> list[dict]:
        def _fetch():
            ticker = yf.Ticker(symbol)
            return ticker.news or []
        return await asyncio.get_event_loop().run_in_executor(None, _fetch)


market_data_service = MarketDataService()
