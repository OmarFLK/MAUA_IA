import { ArrowLeft, Menu } from 'lucide-react'
import type { ReactNode } from 'react'

export type WorkspaceNavigationProps = {
  onBack: () => void
  onOpenMenu: () => void
}

type Props = WorkspaceNavigationProps & {
  title: string
  subtitle?: string
  className?: string
  children?: ReactNode
}

export default function WorkspaceHeader({ title, subtitle, className = '', children, onBack, onOpenMenu }: Props) {
  return (
    <header className={`workspace-header ${className}`}>
      <div className="header-leading">
        <button className="icon-button navigation-back" type="button" onClick={onBack} aria-label="Voltar" title="Voltar"><ArrowLeft size={20} /></button>
        <div className="header-title"><strong>{title}</strong>{subtitle && <span>{subtitle}</span>}</div>
      </div>
      <div className="header-actions">
        {children}
        <button className="icon-button navigation-menu mobile-menu" type="button" onClick={onOpenMenu} aria-label="Abrir menu" title="Abrir menu"><Menu size={21} /></button>
      </div>
    </header>
  )
}
