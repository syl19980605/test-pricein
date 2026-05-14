import { useState } from 'react'
import { useChat } from '../../hooks/useChat'
import Sidebar from './Sidebar'
import Header from './Header'
import DashboardPanel from '../dashboard/DashboardPanel'
import ChatPanel from '../chat/ChatPanel'
import MonitorsPanel from '../monitors/MonitorsPanel'
import PositionsPanel from '../positions/PositionsPanel'

const TAB_TITLES: Record<string, string> = {
  dashboard: '资产仪表盘',
  chat: 'Bobby AI Agent',
  monitors: '标的监控',
  positions: '模拟持仓',
}

export default function AppLayout() {
  const [activeTab, setActiveTab] = useState('dashboard')
  // useChat 提升到这里，AppLayout 始终挂载，切 tab 不会丢失对话历史
  const chat = useChat()

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header title={TAB_TITLES[activeTab] || 'Bobby AI'} />
        {/* main 是 flex 列容器；各面板用 flex-1 填满，不再依赖 h-full 百分比链 */}
        <main className="flex-1 min-h-0 flex flex-col">
          {activeTab === 'dashboard' && (
            <div className="flex-1 overflow-auto p-6">
              <DashboardPanel />
            </div>
          )}
          {activeTab === 'chat' && (
            <ChatPanel
              messages={chat.messages}
              isStreaming={chat.isStreaming}
              sendMessage={chat.sendMessage}
              onClearHistory={chat.clearHistory}
            />
          )}
          {activeTab === 'monitors' && (
            <div className="flex-1 overflow-auto p-6">
              <MonitorsPanel />
            </div>
          )}
          {activeTab === 'positions' && (
            <div className="flex-1 overflow-auto p-6">
              <PositionsPanel />
            </div>
          )}
        </main>
      </div>
    </div>
  )
}
