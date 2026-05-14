import { Activity } from 'lucide-react'

interface HeaderProps {
  title: string
}

export default function Header({ title }: HeaderProps) {
  return (
    <header className="h-16 px-6 flex items-center justify-between border-b border-border bg-surface-light">
      <h1 className="text-lg font-semibold text-text-primary">{title}</h1>
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 text-sm text-accent-green">
          <Activity size={14} />
          <span>Live</span>
        </div>
        <div className="text-xs text-text-secondary">
          Bobby AI Demo
        </div>
      </div>
    </header>
  )
}
