import { Activity, ChevronDown, Cpu, Database, Server, XCircle } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { modelDisplayName } from '../../lib/models'
import type { AvailableModel, Health } from '../../types'

type Props = {
  health: Health | null
  connectionError: boolean
  models: AvailableModel[]
}

export default function ModelStatus({ health, connectionError, models }: Props) {
  const [open, setOpen] = useState(false)
  const wrapperRef = useRef<HTMLDivElement>(null)
  const status = connectionError ? 'offline' : !health ? 'connecting' : health.configured ? 'online' : health.analytics_ready ? 'degraded' : 'offline'
  const labels = { online: 'Online', offline: 'Offline', degraded: 'Parcial', connecting: 'Conectando' }

  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (!wrapperRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [])

  return (
    <div className="model-status-wrap" ref={wrapperRef}>
      <button className="model-status-button" onClick={() => setOpen((value) => !value)} aria-expanded={open}>
        <span className={`status-indicator ${status}`} />
        <span><strong>{modelDisplayName(health?.model)}</strong><small>Endpoint institucional · {labels[status]}</small></span>
        <ChevronDown size={15} className={open ? 'rotate' : ''} />
      </button>
      {open && (
        <div className="model-popover" role="dialog" aria-label="Detalhes do modelo">
          <header><span><Activity size={16} /> Status do modelo</span><strong className={status}>{labels[status]}</strong></header>
          <dl>
            <div><dt><Cpu size={14} /> Modelo</dt><dd>{modelDisplayName(health?.model)}</dd></div>
            <div><dt><Server size={14} /> Provider</dt><dd>Endpoint institucional</dd></div>
            <div><dt><Database size={14} /> Base analítica</dt><dd>{health?.analytics_ready ? 'Disponível' : 'Indisponível'}</dd></div>
            <div><dt><XCircle size={14} /> Runtime</dt><dd>Não informado</dd></div>
          </dl>
          {models.length > 0 && <p>{models.length} {models.length === 1 ? 'modelo disponível' : 'modelos disponíveis'} no endpoint.</p>}
        </div>
      )}
    </div>
  )
}
