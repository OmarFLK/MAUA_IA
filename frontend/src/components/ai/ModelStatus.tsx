import { Check, ChevronDown, Cpu, Network, Server, Sparkles } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { modelDisplayName } from '../../lib/models'
import type { AssistantMode, AvailableModel, Health } from '../../types'

type Props = {
  health: Health | null
  connectionError: boolean
  models: AvailableModel[]
  assistantMode: AssistantMode
  onAssistantChange: (mode: AssistantMode) => void
}

const assistants = {
  cmob: {
    name: 'CMob AI',
    description: 'Análise inteligente de mobilidade',
    icon: Network,
  },
  general: {
    name: 'Gemma Livre',
    description: 'Assistente de propósito geral',
    icon: Sparkles,
  },
} satisfies Record<AssistantMode, { name: string; description: string; icon: typeof Network }>

export default function ModelStatus({ health, connectionError, models, assistantMode, onAssistantChange }: Props) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const status = connectionError ? 'offline' : !health ? 'connecting' : health.configured ? 'online' : health.analytics_ready ? 'degraded' : 'offline'
  const labels = { online: 'Online', offline: 'Offline', degraded: 'Parcial', connecting: 'Conectando' }
  const selected = assistants[assistantMode]

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  function select(mode: AssistantMode) {
    onAssistantChange(mode)
    setOpen(false)
  }

  return (
    <div className="model-status-wrap" ref={wrapperRef}>
      <button className="model-status-button" onClick={() => setOpen((value) => !value)} aria-expanded={open} aria-label="Escolher assistente">
        <span className={`status-indicator ${status}`} />
        <span><strong>{selected.name}</strong><small>{modelDisplayName(health?.model)} · {labels[status]}</small></span>
        <ChevronDown size={15} className={open ? 'rotate' : ''} />
      </button>
      {open && (
        <div className="model-popover assistant-popover" role="dialog" aria-label="Escolher assistente">
          <header><span>Escolher assistente</span><strong className={status}>{labels[status]}</strong></header>
          <div className="assistant-options">
            {(Object.keys(assistants) as AssistantMode[]).map((mode) => {
              const item = assistants[mode]
              const Icon = item.icon
              return (
                <button key={mode} className={assistantMode === mode ? 'active' : ''} onClick={() => select(mode)}>
                  <span className="assistant-option-icon"><Icon size={17} /></span>
                  <span><strong>{item.name}</strong><small>{item.description}</small><em>{modelDisplayName(health?.model)}</em></span>
                  {assistantMode === mode && <Check size={16} />}
                </button>
              )
            })}
          </div>
          <dl className="assistant-model-details">
            <div><dt><Cpu size={14} /> Modelo</dt><dd>{modelDisplayName(health?.model)}</dd></div>
            <div><dt><Server size={14} /> Provider</dt><dd>Endpoint institucional</dd></div>
          </dl>
          {models.length > 0 && <p>{models.length} {models.length === 1 ? 'modelo disponível' : 'modelos disponíveis'} no endpoint.</p>}
        </div>
      )}
    </div>
  )
}
