import { Clock3, MessageSquareText, Pencil, Search, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'
import type { AssistantMode, Conversation, UserSettings } from '../../types'
import WorkspaceHeader, { type WorkspaceNavigationProps } from '../ui/WorkspaceHeader'

type Props = WorkspaceNavigationProps & {
  conversations: Conversation[]
  assistantMode: AssistantMode
  settings: UserSettings
  onOpen: (id: string) => void
  onDelete: (id: string) => void
  onRename: (id: string, title: string) => void
}

export default function HistoryPage({ conversations, assistantMode, settings, onOpen, onDelete, onRename, onBack, onOpenMenu }: Props) {
  const [search, setSearch] = useState('')
  const [showAll, setShowAll] = useState(false)
  const visible = useMemo(
    () => conversations
      .filter((item) => showAll || item.assistantMode === assistantMode)
      .filter((item) => `${item.title} ${item.messages.map((message) => message.content).join(' ')}`.toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR')))
      .sort((a, b) => b.updatedAt - a.updatedAt),
    [assistantMode, conversations, search, showAll],
  )
  const format = (timestamp: number) => settings.dateFormat === 'YYYY-MM-DD' ? new Date(timestamp).toISOString().slice(0, 10) : new Date(timestamp).toLocaleDateString('pt-BR')
  const activeName = assistantMode === 'cmob' ? 'CMob AI' : 'Gemma Livre'

  return (
    <main className="workspace page-workspace">
      <WorkspaceHeader title="Histórico" subtitle={`${visible.length} ${visible.length === 1 ? 'conversa exibida' : 'conversas exibidas'}`} onBack={onBack} onOpenMenu={onOpenMenu} />
      <section className="content-page">
        <div className="page-heading">
          <div><p className="section-kicker">CONVERSAS</p><h1>Seu histórico</h1></div>
          <div className="history-page-tools">
            <div className="segmented-control"><button className={!showAll ? 'active' : ''} onClick={() => setShowAll(false)}>{activeName}</button><button className={showAll ? 'active' : ''} onClick={() => setShowAll(true)}>Todos</button></div>
            <label className="page-search"><Search size={16} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar no histórico" /></label>
          </div>
        </div>
        <div className="list-panel">
          {visible.map((conversation) => (
            <article className="conversation-list-item" key={conversation.id}>
              <button className="conversation-open" onClick={() => onOpen(conversation.id)}>
                <span className="list-icon"><MessageSquareText size={17} /></span>
                <span className="conversation-copy"><strong>{conversation.title}</strong><small>{conversation.messages.length} mensagens · Atualizada em {format(conversation.updatedAt)}</small></span>
                <span className={`assistant-tag ${conversation.assistantMode}`}>{conversation.assistantMode === 'cmob' ? 'CMob AI' : 'Gemma Livre'}</span>
              </button>
              <div className="row-actions"><button onClick={() => { const title = window.prompt('Novo título', conversation.title); if (title?.trim()) onRename(conversation.id, title.trim()) }} aria-label="Renomear"><Pencil size={15} /></button><button onClick={() => onDelete(conversation.id)} aria-label="Excluir"><Trash2 size={15} /></button></div>
            </article>
          ))}
          {!visible.length && <div className="page-empty"><Clock3 size={24} /><strong>Nenhuma conversa encontrada</strong><span>Tente buscar por outro termo.</span></div>}
        </div>
      </section>
    </main>
  )
}
