from datetime import datetime

import pandas as pd
import ta

from backend.models.schemas import IndicatorSet
from backend.services.market_data import market_data_service


class TechnicalService:
    async def calculate_all(self, symbol: str, period: str = "3mo") -> IndicatorSet:
        df = await market_data_service.get_price_history(symbol, period)
        if df.empty or len(df) < 20:
            return IndicatorSet(symbol=symbol, timestamp=datetime.utcnow())

        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        rsi = ta.momentum.RSIIndicator(close, window=14)
        macd_ind = ta.trend.MACD(close, window_slow=26, window_fast=12, window_sign=9)
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2)
        atr = ta.volatility.AverageTrueRange(high, low, close, window=14)

        sma_20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
        sma_50 = ta.trend.SMAIndicator(close, window=min(50, len(close))).sma_indicator()
        ema_12 = ta.trend.EMAIndicator(close, window=12).ema_indicator()
        ema_26 = ta.trend.EMAIndicator(close, window=min(26, len(close))).ema_indicator()
        vol_sma = ta.trend.SMAIndicator(volume, window=min(20, len(volume))).sma_indicator()

        def safe_last(series):
            val = series.iloc[-1] if not series.empty else None
            if val is not None and pd.notna(val):
                return round(float(val), 4)
            return None

        return IndicatorSet(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            rsi_14=safe_last(rsi.rsi()),
            macd=safe_last(macd_ind.macd()),
            macd_signal=safe_last(macd_ind.macd_signal()),
            macd_histogram=safe_last(macd_ind.macd_diff()),
            sma_20=safe_last(sma_20),
            sma_50=safe_last(sma_50),
            ema_12=safe_last(ema_12),
            ema_26=safe_last(ema_26),
            bollinger_upper=safe_last(bb.bollinger_hband()),
            bollinger_lower=safe_last(bb.bollinger_lband()),
            atr_14=safe_last(atr.average_true_range()),
            volume_sma_20=safe_last(vol_sma),
        )


technical_service = TechnicalService()
