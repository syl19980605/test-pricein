import { LayoutDashboard, MessageCircle, Radar, Briefcase } from 'lucide-react'
import clsx from 'clsx'

const NAV_ITEMS = [
  { id: 'dashboard', icon: LayoutDashboard, label: '仪表盘' },
  { id: 'chat', icon: MessageCircle, label: 'Bobby' },
  { id: 'monitors', icon: Radar, label: '监控' },
  { id: 'positions', icon: Briefcase, label: '持仓' },
] as const

interface SidebarProps {
  activeTab: string
  onTabChange: (tab: string) => void
}

export default function Sidebar({ activeTab, onTabChange }: SidebarProps) {
  return (
    <aside className="w-20 bg-surface-light flex flex-col items-center py-6 border-r border-border">
      <div className="text-2xl font-bold text-primary mb-10">B</div>
      <nav className="flex flex-col gap-2 flex-1">
        {NAV_ITEMS.map(({ id, icon: Icon, label }) => (
          <button
            key={id}
            onClick={() => onTabChange(id)}
            className={clsx(
              'flex flex-col items-center gap-1 px-3 py-3 rounded-xl text-xs transition-all cursor-pointer',
              activeTab === id
                ? 'bg-primary/20 text-primary'
                : 'text-text-secondary hover:text-text-primary hover:bg-surface-lighter'
            )}
          >
            <Icon size={22} />
            <span>{label}</span>
          </button>
        ))}
      </nav>
    </aside>
  )
}
