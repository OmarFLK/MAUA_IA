import { BarChart3, BrainCircuit, MessageSquareText } from 'lucide-react'
import type { Conversation } from '../../types'

export function AnalysesPage({ conversations, onOpen }: { conversations: Conversation[]; onOpen: (id: string) => void }) {
  const withAnswers = conversations.filter((conversation) => conversation.messages.some((message) => message.role === 'assistant' && !message.error))
  return <main className="workspace page-workspace"><header className="workspace-header"><div className="header-title"><strong>Análises</strong><span>Respostas produzidas nas suas conversas</span></div></header><section className="content-page"><div className="page-heading"><div><p className="section-kicker">CONTEÚDO REAL</p><h1>Análises recentes</h1><p>Esta página reúne conversas que já possuem respostas da cMob AI.</p></div></div><div className="analysis-grid">{withAnswers.map((conversation) => { const answers = conversation.messages.filter((message) => message.role === 'assistant' && !message.error); const last = answers.at(-1); return <button key={conversation.id} onClick={() => onOpen(conversation.id)}><BarChart3 size={18} /><strong>{conversation.title}</strong><span>{last?.content.slice(0, 150)}{(last?.content.length ?? 0) > 150 ? '…' : ''}</span><small>{answers.length} {answers.length === 1 ? 'resposta' : 'respostas'}</small></button> })}{!withAnswers.length && <div className="page-empty full"><BarChart3 size={25} /><strong>Nenhuma análise disponível</strong><span>As respostas geradas no chat aparecerão aqui.</span></div>}</div></section></main>
}

export function MemoryPage({ conversations }: { conversations: Conversation[] }) {
  const messageCount = conversations.reduce((sum, conversation) => sum + conversation.messages.length, 0)
  return <main className="workspace page-workspace"><header className="workspace-header"><div className="header-title"><strong>Memória</strong><span>Histórico da conta</span></div></header><section className="content-page"><div className="page-heading"><div><p className="section-kicker">CONTA</p><h1>Histórico salvo</h1></div></div><div className="memory-summary"><div><MessageSquareText size={20} /><span><strong>{conversations.length}</strong> conversas</span></div><div><BrainCircuit size={20} /><span><strong>{messageCount}</strong> mensagens</span></div></div></section></main>
}
