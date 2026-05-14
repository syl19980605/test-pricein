export interface Asset {
  symbol: string
  name: string
  asset_class: string
  current_price: number
  change_24h_pct: number
  volume_24h: number | null
  market_cap: number | null
  last_updated: string
  price_history_7d: number[]
}

export interface IndicatorSet {
  symbol: string
  timestamp: string
  rsi_14: number | null
  macd: number | null
  macd_signal: number | null
  macd_histogram: number | null
  sma_20: number | null
  sma_50: number | null
  ema_12: number | null
  ema_26: number | null
  bollinger_upper: number | null
  bollinger_lower: number | null
  atr_14: number | null
  volume_sma_20: number | null
}

export type SignalDirection = 'strong_buy' | 'buy' | 'neutral' | 'sell' | 'strong_sell'

export interface Signal {
  symbol: string
  direction: SignalDirection
  confidence: number
  technical_score: number
  sentiment_score: number
  priced_in_score: number
  reasoning: string
  triggered_at: string
  key_factors: string[]
}

export interface StrategyCardData {
  title: string
  symbols: string[]
  allocation: Record<string, number>
  expected_return_annual: number | null
  max_drawdown: number | null
  sharpe_ratio: number | null
  risk_level: string
  reasoning: string
  entry_conditions: string[]
  exit_conditions: string[]
}

export interface Alert {
  id: string
  symbol: string
  alert_type: string
  severity: 'info' | 'warning' | 'critical'
  title: string
  message: string
  data: Record<string, unknown> | null
  created_at: string
  acknowledged: boolean
}

export interface Position {
  id: string
  symbol: string
  name: string
  direction: string
  entry_price: number
  current_price: number
  quantity: number
  stop_loss: number | null
  take_profit: number | null
  status: string
  opened_at: string
  pnl: number
  pnl_pct: number
}

// ── 消息定价场景 ──

export interface NewsImpactItem {
  title: string
  source: string
  published_at: string | null
  impact_direction: 'bullish' | 'bearish' | 'neutral'
  impact_summary: string
  priced_in_pct: number
  horizon: 'short' | 'mid' | 'long' | null
}

export type Horizon = 'short' | 'mid' | 'long'

export interface PredictionMarketItem {
  factor: string
  market_question: string
  probability: number
  volume: number
  end_date: string
  slug: string
  sell_the_fact_risk: 'low' | 'medium' | 'high'
  relevance: number       // r_i
  confidence: number      // c_i（成交量+新鲜度）
  horizon_match: number   // h_i（结算日期 vs 持有期）
  weight: number          // r·c·h
}

export interface PredictionMarketBasket {
  matched: boolean
  reason: string
  horizon: Horizon
  factors_searched: string[]
  items: PredictionMarketItem[]
  aggregate_priced_in: number
  overall_confidence: number
  summary: string
}

export interface NewsImpactResult {
  symbol: string
  name: string
  user_thesis: string
  user_direction: 'bullish' | 'bearish'
  horizon: Horizon
  logic_verdict: 'supports' | 'partially' | 'contradicts'
  logic_assessment: string
  hypothesis_given: boolean
  event_priced_in_pct: number
  related_news: NewsImpactItem[]
  overall_direction: 'bullish' | 'bearish' | 'neutral'
  summary: string
}

export interface Monitor {
  id: string
  symbol: string
  name: string
  thesis: string
  direction: 'bullish' | 'bearish'
  horizon: 'short' | 'mid' | 'long' | null
  refresh_interval_min: number
  status: string
  created_at: string
  last_refreshed_at: string
  news: NewsImpactItem[]
  signal_direction: SignalDirection | null
  signal_priced_in: number | null
}

export interface AskAction {
  tool: string
  args: Record<string, unknown>
}

export interface AskOption {
  label: string
  message: string
  variant: 'primary' | 'default'
  action?: AskAction | null
}

export interface AskBlock {
  question: string
  options: AskOption[]
}

export type CardPayload =
  | { type: 'signal'; data: Signal }
  | { type: 'strategy'; data: StrategyCardData }
  | { type: 'news_impact'; data: NewsImpactResult }
  | { type: 'prediction_market'; data: PredictionMarketBasket }
  | { type: 'monitor'; data: Monitor }
  | { type: 'ask'; data: AskBlock }

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  cards: CardPayload[]
  toolCalls: { tool: string; args: Record<string, unknown> }[]
  streaming?: boolean
}

export type StreamChunk =
  | { type: 'conversation_id'; conversation_id: string }
  | { type: 'text'; content: string }
  | { type: 'tool_call'; tool: string; args: Record<string, unknown> }
  | { type: 'card'; card: CardPayload }
  | { type: 'done' }
  | { type: 'error'; message: string }
