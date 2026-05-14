from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel


class AssetClass(str, Enum):
    A_SHARE = "a_share"
    US_STOCK = "us_stock"
    CRYPTO = "crypto"
    COMMODITY = "commodity"


class SignalDirection(str, Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    NEUTRAL = "neutral"
    SELL = "sell"
    STRONG_SELL = "strong_sell"


class AlertType(str, Enum):
    PRICE_MOVE = "price_move"
    NEWS_SENTIMENT = "news_sentiment"
    INDICATOR_CROSS = "indicator_cross"
    PRICED_IN_SHIFT = "priced_in_shift"
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"


# ── Asset ──

class Asset(BaseModel):
    symbol: str
    name: str
    asset_class: AssetClass
    current_price: float
    change_24h_pct: float
    volume_24h: Optional[float] = None
    market_cap: Optional[float] = None
    last_updated: datetime


class AssetDetail(Asset):
    price_history_7d: list[float] = []
    indicators: Optional["IndicatorSet"] = None
    latest_signal: Optional["Signal"] = None
    news_count_24h: int = 0


# ── Technical Indicators ──

class IndicatorSet(BaseModel):
    symbol: str
    timestamp: datetime
    rsi_14: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_histogram: Optional[float] = None
    sma_20: Optional[float] = None
    sma_50: Optional[float] = None
    ema_12: Optional[float] = None
    ema_26: Optional[float] = None
    bollinger_upper: Optional[float] = None
    bollinger_lower: Optional[float] = None
    atr_14: Optional[float] = None
    volume_sma_20: Optional[float] = None


# ── News ──

class NewsItem(BaseModel):
    title: str
    source: str
    url: str
    published_at: datetime
    summary: Optional[str] = None
    sentiment_score: Optional[float] = None
    relevance_score: Optional[float] = None
    priced_in_probability: Optional[float] = None


# ── Signal ──

class Signal(BaseModel):
    symbol: str
    direction: SignalDirection
    confidence: float
    technical_score: float
    sentiment_score: float
    priced_in_score: float
    reasoning: str
    triggered_at: datetime
    key_factors: list[str] = []


# ── Position ──

class Position(BaseModel):
    id: str
    symbol: str
    direction: str
    entry_price: float
    current_price: float
    quantity: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    pnl: float
    pnl_pct: float
    opened_at: datetime
    status: str = "open"


class PositionCreate(BaseModel):
    symbol: str
    direction: str = "long"
    quantity: float = 1.0
    stop_loss_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None


# ── Alert ──

class Alert(BaseModel):
    id: str
    symbol: str
    alert_type: AlertType
    severity: str = "info"
    title: str
    message: str
    data: Optional[dict] = None
    created_at: datetime
    acknowledged: bool = False


# ── Chat ──
# ChatRequest 定义在文件末尾（依赖 AskAction）

class ChatMessage(BaseModel):
    role: str
    content: str
    timestamp: datetime
    metadata: Optional[dict] = None


# ── Strategy Card ──

class StrategyCard(BaseModel):
    title: str
    symbols: list[str]
    allocation: dict[str, float]
    expected_return_annual: Optional[float] = None
    max_drawdown: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    risk_level: str = "moderate"
    reasoning: str = ""
    entry_conditions: list[str] = []
    exit_conditions: list[str] = []
    backtest_summary: Optional[dict] = None


# ── 消息定价场景：新闻影响分析 ──

class NewsImpactItem(BaseModel):
    title: str
    source: str = ""
    published_at: Optional[str] = None
    impact_direction: str = "neutral"   # bullish / bearish / neutral
    impact_summary: str = ""             # 这条消息对标的的影响逻辑
    priced_in_pct: float = 0.5           # 0~1，已定价程度
    horizon: Optional[str] = None        # short / mid / long（horizon 分类后填充）


class PredictionMarketItem(BaseModel):
    """单个匹配到的预测市场。priced-in 度由 P 给出，
    它在篮子里的权重 = relevance × confidence × horizon_match。"""
    factor: str = ""                     # 这个市场回答的驱动因素，如"美联储降息"
    market_question: str = ""            # Polymarket 市场问题
    probability: float = 0.5             # Yes 概率（≈该因素被定价的程度，原始信号不扭曲）
    volume: float = 0.0
    end_date: str = ""
    slug: str = ""
    sell_the_fact_risk: str = "low"      # low / medium / high —— P 越高，'卖事实'风险越大
    # ── 三个权重维度 ──
    relevance: float = 0.5               # r_i：该因素对标的有多相关（LLM 判断）
    confidence: float = 0.5              # c_i：对这个测量的置信度（成交量+新鲜度）
    horizon_match: float = 0.5           # h_i：结算日期与用户持有期的匹配度
    weight: float = 0.0                  # r·c·h，该市场在聚合里的最终权重


class PredictionMarketBasket(BaseModel):
    """预测市场篮子：把标的的价格驱动因素拆解后，逐个去 Polymarket 搜索，
    聚合成一篮子信号。这是和传统量化最不一样的维度 —— 量化看后视的价格/指标，
    预测市场是市场用真金白银投出的前视'预期'。

    aggregate_priced_in = Σ(P·r·c·h) / Σ(r·c·h) —— 确定性公式，可审计。"""
    matched: bool = False                # 是否匹配到任何预测市场
    reason: str = ""                     # 未匹配时的说明
    horizon: str = "mid"                 # 用户的持有期 short/mid/long（决定 h_i）
    factors_searched: list[str] = []     # 拆解出的驱动因素（检索词）
    items: list[PredictionMarketItem] = []   # 匹配到的市场篮子
    aggregate_priced_in: float = 0.5     # 篮子聚合的"已定价程度"（加权平均）
    overall_confidence: float = 0.0      # 整体可信度（基于篮子的成交量/权重）
    summary: str = ""                    # LLM 对整个篮子的定价含义解读


class NewsImpactResult(BaseModel):
    symbol: str
    name: str = ""
    user_thesis: str = ""                # 用户提到的消息内容
    user_direction: str = "bullish"      # 影响方向 bullish/bearish（用户给的或 Bobby 判的）
    hypothesis_given: bool = True        # 用户是否给了判断方向（否=Bobby 自己判的）
    horizon: str = "mid"                 # 用户的持有期 short/mid/long（前置参数）
    logic_verdict: str = "partially"     # supports / partially / contradicts
    logic_assessment: str = ""           # 对消息影响逻辑的点评（结合持有期）
    event_priced_in_pct: float = 0.5     # 这条消息的已定价程度（LLM 估计）
    related_news: list[NewsImpactItem] = []   # 更大范围检索到的其他影响消息
    overall_direction: str = "neutral"   # 综合方向
    summary: str = ""


# ── 消息定价场景：监控 ──

class Monitor(BaseModel):
    id: str
    symbol: str
    name: str = ""
    thesis: str = ""
    direction: str = "bullish"
    horizon: Optional[str] = None        # short / mid / long
    refresh_interval_min: int = 60
    status: str = "active"
    created_at: str = ""
    last_refreshed_at: str = ""
    news: list[NewsImpactItem] = []      # 截至当前的价格影响消息+信号+定价程度
    signal_direction: Optional[str] = None
    signal_priced_in: Optional[float] = None


# ── 消息定价场景：交互式 Ask 组件 ──

class AskAction(BaseModel):
    """结构化 action：点击带 action 的 ask 选项时，后端直接、确定性地执行此工具，
    不经过 MiMo 的工具选择（MiMo 仅负责事后用自然语言解读结果）。"""
    tool: str                  # 要执行的工具名
    args: dict = {}            # 工具参数（emit ask 卡片时即已知，预填好）

class AskOption(BaseModel):
    label: str           # 按钮显示文字
    message: str         # 点击后展示为用户消息气泡的文字
    variant: str = "default"   # primary / default
    action: Optional[AskAction] = None   # 有 action = 确定性执行；无 action = 走 MiMo

class AskBlock(BaseModel):
    question: str
    options: list[AskOption] = []


class ChatRequest(BaseModel):
    message: str
    conversation_id: Optional[str] = None
    action: Optional[AskAction] = None   # ask 按钮点击时携带的结构化 action
