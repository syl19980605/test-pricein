import type { ChatMessage } from '../../api/types'
import SignalCard from './SignalCard'
import StrategyCard from './StrategyCard'
import NewsImpactCard from './NewsImpactCard'
import PredictionMarketCard from './PredictionMarketCard'
import MonitorCard from './MonitorCard'
import AskCard from './AskCard'
import Markdown from '../common/Markdown'
import { Loader2, Wrench } from 'lucide-react'

const TOOL_LABELS: Record<string, string> = {
  get_asset_price: '查询行情',
  get_technical_indicators: '计算技术指标',
  analyze_news_sentiment: '分析新闻情绪',
  generate_strategy_card: '生成策略卡片',
  begin_analysis: '确认投资持有期',
  analyze_asset: '综合分析',
  create_monitor: '创建监控',
  manage_position: '管理持仓',
}

interface MessageBubbleProps {
  message: ChatMessage
  onSend?: (text: string, action?: import('../../api/types').AskAction | null) => void
}

export default function MessageBubble({ message, onSend }: MessageBubbleProps) {
  const isUser = message.role === 'user'

  if (isUser) {
    return (
      <div className="flex justify-end">
        <div className="bg-primary text-white rounded-2xl rounded-br-md px-4 py-2.5 max-w-lg">
          {message.content}
        </div>
      </div>
    )
  }

  return (
    <div className="flex gap-3">
      <div className="w-8 h-8 rounded-full bg-primary/20 text-primary flex items-center justify-center font-bold text-sm shrink-0">
        B
      </div>
      <div className="flex-1 min-w-0">
        {message.toolCalls.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {message.toolCalls.map((tc, i) => (
              <span
                key={i}
                className="flex items-center gap-1 text-[10px] bg-surface-lighter text-text-secondary px-2 py-0.5 rounded-full"
              >
                <Wrench size={9} />
                {TOOL_LABELS[tc.tool] || tc.tool}
              </span>
            ))}
          </div>
        )}

        {message.content && (
          <div className="bg-surface-light rounded-2xl rounded-tl-md px-4 py-2.5 inline-block max-w-full">
            <Markdown>{message.content}</Markdown>
            {message.streaming && (
              <span className="inline-block w-1.5 h-4 bg-primary/60 ml-0.5 animate-pulse align-middle" />
            )}
          </div>
        )}

        {message.streaming && !message.content && (
          <div className="flex items-center gap-2 text-text-secondary text-sm py-2">
            <Loader2 size={14} className="animate-spin" />
            Bobby 正在思考...
          </div>
        )}

        {message.cards.map((card, i) => {
          if (card.type === 'signal') return <SignalCard key={i} data={card.data} />
          if (card.type === 'strategy') return <StrategyCard key={i} data={card.data} />
          if (card.type === 'news_impact') return <NewsImpactCard key={i} data={card.data} />
          if (card.type === 'prediction_market') return <PredictionMarketCard key={i} data={card.data} />
          if (card.type === 'monitor') return <MonitorCard key={i} data={card.data} />
          if (card.type === 'ask') return <AskCard key={i} data={card.data} onSend={onSend} />
          return null
        })}
      </div>
    </div>
  )
}
