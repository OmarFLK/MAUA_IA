import { Activity, Cpu, Gauge, Server, ShieldCheck, Timer, Waypoints } from 'lucide-react'
import { modelDisplayName } from '../../lib/models'
import type { AvailableModel, AppView, Health, UsageRecord, UserSettings } from '../../types'
import Toggle from '../ui/Toggle'
import WorkspaceHeader, { type WorkspaceNavigationProps } from '../ui/WorkspaceHeader'

type Props = WorkspaceNavigationProps & {
  view: AppView
  isAdmin: boolean
  health: Health | null
  models: AvailableModel[]
  usageRecords: UsageRecord[]
  settings: UserSettings
  onSettings: (settings: UserSettings) => void
}

function Metric({ icon: Icon, label, value, detail }: { icon: typeof Activity; label: string; value: string; detail?: string }) {
  return <div className="metric-card"><Icon size={18} /><span>{label}</span><strong>{value}</strong>{detail && <small>{detail}</small>}</div>
}

function Unavailable({ label }: { label: string }) {
  return <div className="technical-row"><span>{label}</span><strong>Não disponível</strong></div>
}

export default function AdminPage(props: Props) {
  if (!props.isAdmin) return <main className="workspace page-workspace"><WorkspaceHeader title="Administração" onBack={props.onBack} onOpenMenu={props.onOpenMenu} /><section className="access-denied"><ShieldCheck size={30} /><h1>Acesso restrito</h1><p>Esta área exige uma função administrativa informada pelo backend.</p></section></main>

  const completed = props.usageRecords.filter((record) => record.status === 'success')
  const tokenTotal = completed.reduce((total, record) => total + (record.usage?.total_tokens ?? 0), 0)
  const avgLatency = completed.length ? completed.reduce((total, record) => total + record.durationMs, 0) / completed.length : null
  const avgTtftRecords = completed.filter((record) => record.ttftMs !== undefined)
  const avgTtft = avgTtftRecords.length ? avgTtftRecords.reduce((total, record) => total + (record.ttftMs ?? 0), 0) / avgTtftRecords.length : null

  return <main className="workspace page-workspace"><WorkspaceHeader title="Administração" subtitle="Diagnóstico baseado nas informações disponíveis" onBack={props.onBack} onOpenMenu={props.onOpenMenu} /><section className="content-page"><div className="page-heading"><div><p className="section-kicker">ADMIN</p><h1>{props.view === 'admin-model' ? 'Modelo e runtime' : props.view === 'admin-ai' ? 'Configurações da IA' : 'Monitoramento'}</h1></div><span className="data-scope">Dados locais e da API</span></div>
    {props.view === 'admin-overview' && <>
      <div className="metrics-grid"><Metric icon={Server} label="API" value={props.health?.status ?? 'Não disponível'} detail="Informado por /api/health" /><Metric icon={Activity} label="Requisições" value={String(props.usageRecords.length)} detail="Neste navegador" /><Metric icon={Waypoints} label="Tokens" value={tokenTotal ? tokenTotal.toLocaleString('pt-BR') : 'Não disponível'} detail="Neste navegador" /><Metric icon={Timer} label="Latência média" value={avgLatency ? `${(avgLatency / 1000).toFixed(2)} s` : 'Não disponível'} detail="Neste navegador" /><Metric icon={Gauge} label="Tempo até resposta" value={avgTtft ? `${(avgTtft / 1000).toFixed(2)} s` : 'Não disponível'} detail="Neste navegador" /></div>
      <div className="admin-columns"><div className="admin-panel"><h2>Serviços</h2><div className="technical-row"><span>Modelo remoto</span><strong>{props.health?.configured ? 'Conectado' : 'Indisponível'}</strong></div><div className="technical-row"><span>Base analítica</span><strong>{props.health?.analytics_ready ? 'Pronta' : 'Indisponível'}</strong></div><div className="technical-row"><span>Banco da aplicação</span><strong>{props.health?.database_ready ? 'Pronto' : 'Indisponível'}</strong></div></div><div className="admin-panel"><h2>Infraestrutura</h2><Unavailable label="Uso de GPU" /><Unavailable label="Uso de VRAM" /><Unavailable label="Uso de RAM do servidor" /><Unavailable label="Uptime" /></div></div>
    </>}
    {props.view === 'admin-model' && <div className="admin-columns"><div className="admin-panel"><h2>Modelos publicados</h2>{props.models.length ? props.models.map((model) => <div className="model-list-row" key={model.id}><Cpu size={17} /><span><strong>{modelDisplayName(model.id)}</strong><small>{model.id}</small></span><b>{model.id === props.health?.model ? 'Em uso' : 'Disponível'}</b></div>) : <p className="panel-empty">A lista de modelos não está disponível para esta sessão.</p>}</div><div className="admin-panel"><h2>Detalhes do runtime</h2><div className="technical-row"><span>Modelo ativo</span><strong>{props.health?.model || 'Não disponível'}</strong></div><div className="technical-row"><span>Raciocínio</span><strong>{props.health ? (props.health.supports_thinking ? 'Disponível' : 'Não informado') : 'Não disponível'}</strong></div><Unavailable label="Quantização" /><Unavailable label="Tokenizer" /><Unavailable label="Janela de contexto" /><Unavailable label="Parâmetros de execução" /></div></div>}
    {props.view === 'admin-ai' && <div className="admin-columns"><div className="admin-panel"><h2>Parâmetros conectados</h2><label className="admin-field"><span>Temperatura</span><input type="number" min="0" max="1" step="0.05" value={props.settings.temperature} onChange={(event) => props.onSettings({ ...props.settings, temperature: Number(event.target.value) })} /></label><label className="admin-field"><span>Máximo de saída</span><input type="number" min="128" max="8192" step="128" value={props.settings.maxTokens} onChange={(event) => props.onSettings({ ...props.settings, maxTokens: Number(event.target.value) })} /></label><div className="admin-field inline"><span>Raciocínio do modelo</span><Toggle checked={props.settings.thinking} onChange={(thinking) => props.onSettings({ ...props.settings, thinking })} disabled={!props.health?.supports_thinking} label="Raciocínio do modelo" /></div></div><div className="admin-panel"><h2>Gerenciado pelo servidor</h2><label className="admin-field"><span>Prompt de sistema</span><textarea value="Gerenciado pelo pipeline seguro do backend" readOnly /></label><label className="admin-field"><span>Top P</span><input value="Não disponível" readOnly /></label><label className="admin-field"><span>Penalidade de repetição</span><input value="Não disponível" readOnly /></label><p className="panel-note">Esses controles só poderão ser editados quando o backend publicar suporte explícito.</p></div></div>}
  </section></main>
}
