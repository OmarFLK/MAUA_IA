import {
  Activity,
  BarChart3,
  BrainCircuit,
  Clock3,
  Cpu,
  LogOut,
  MessageSquareText,
  MoreHorizontal,
  Network,
  Pencil,
  Plus,
  Search,
  Settings,
  ShieldCheck,
  Sparkles,
  Trash2,
  X,
} from 'lucide-react'
import { useMemo, useState } from 'react'
import type { AuthUser } from '../../AuthScreen'
import type { AppView, AssistantMode, Conversation, LocalProfile } from '../../types'
import Brand from '../ui/Brand'
import UserAvatar from '../ui/UserAvatar'

type Props = {
  view: AppView
  conversations: Conversation[]
  activeId: string
  user: AuthUser
  profile: LocalProfile
  isAdmin: boolean
  mobileOpen: boolean
  assistantMode: AssistantMode
  onCloseMobile: () => void
  onNavigate: (view: AppView) => void
  onNewChat: () => void
  onSelectConversation: (id: string) => void
  onDeleteConversation: (id: string) => void
  onRenameConversation: (id: string, title: string) => void
  onLogout: () => void
}

type Group = { label: string; items: Conversation[] }

function groupedHistory(conversations: Conversation[]): Group[] {
  const now = new Date()
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime()
  const startYesterday = startToday - 86_400_000
  const groups: Group[] = [
    { label: 'Hoje', items: [] },
    { label: 'Ontem', items: [] },
    { label: 'Anteriores', items: [] },
  ]
  conversations.forEach((conversation) => {
    if (conversation.updatedAt >= startToday) groups[0].items.push(conversation)
    else if (conversation.updatedAt >= startYesterday) groups[1].items.push(conversation)
    else groups[2].items.push(conversation)
  })
  return groups.filter((group) => group.items.length)
}

export default function Sidebar(props: Props) {
  const [search, setSearch] = useState('')
  const [profileOpen, setProfileOpen] = useState(false)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [draftTitle, setDraftTitle] = useState('')
  const filtered = useMemo(
    () => props.conversations.filter((item) => item.title.toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR'))).sort((a, b) => b.updatedAt - a.updatedAt),
    [props.conversations, search],
  )
  const mainNav = [
    { id: 'chat' as const, label: 'Chat', icon: MessageSquareText },
    { id: 'history' as const, label: 'Histórico', icon: Clock3 },
    ...(props.assistantMode === 'cmob' ? [
      { id: 'analyses' as const, label: 'Análises', icon: BarChart3 },
      { id: 'memory' as const, label: 'Memória', icon: BrainCircuit },
    ] : []),
  ]

  function navigate(view: AppView) {
    props.onNavigate(view)
    props.onCloseMobile()
  }

  function startRename(conversation: Conversation) {
    setEditingId(conversation.id)
    setDraftTitle(conversation.title)
  }

  function finishRename() {
    if (editingId && draftTitle.trim()) props.onRenameConversation(editingId, draftTitle.trim())
    setEditingId(null)
  }

  return (
    <aside className={`sidebar-v2 ${props.mobileOpen ? 'is-open' : ''}`}>
      <div className="sidebar-brand-row"><Brand /><button className="icon-button mobile-only" onClick={props.onCloseMobile} aria-label="Fechar menu"><X size={18} /></button></div>
      <div className={`sidebar-assistant-badge ${props.assistantMode}`}>
        {props.assistantMode === 'cmob' ? <Network size={13} /> : <Sparkles size={13} />}
        <span>{props.assistantMode === 'cmob' ? 'CMob' : 'Livre'}</span>
      </div>
      <button className="primary-action" onClick={props.onNewChat}><Plus size={17} /> Novo chat</button>

      <nav className="sidebar-nav" aria-label="Navegação principal">
        {mainNav.map(({ id, label, icon: Icon }) => (
          <button key={id} className={props.view === id ? 'active' : ''} onClick={() => navigate(id)}><Icon size={17} /><span>{label}</span></button>
        ))}
      </nav>

      <div className="sidebar-history">
        <div className="sidebar-section-title"><span>Conversas</span><button onClick={() => navigate('history')} aria-label="Ver todo o histórico"><MoreHorizontal size={16} /></button></div>
        <label className="sidebar-search"><Search size={14} /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Buscar conversas" aria-label="Buscar conversas" /></label>
        <div className="history-scroll">
          {groupedHistory(filtered).map((group) => (
            <section key={group.label} className="history-group">
              <h3>{group.label}</h3>
              {group.items.slice(0, 8).map((conversation) => (
                <div className={`history-row ${conversation.id === props.activeId && props.view === 'chat' ? 'active' : ''}`} key={conversation.id}>
                  {editingId === conversation.id ? (
                    <input className="rename-input" value={draftTitle} onChange={(event) => setDraftTitle(event.target.value)} onBlur={finishRename} onKeyDown={(event) => { if (event.key === 'Enter') finishRename(); if (event.key === 'Escape') setEditingId(null) }} autoFocus />
                  ) : (
                    <button className="history-main" onClick={() => props.onSelectConversation(conversation.id)}><MessageSquareText size={14} /><span>{conversation.title}</span></button>
                  )}
                  {editingId !== conversation.id && <div className="history-actions"><button onClick={() => startRename(conversation)} aria-label="Renomear conversa"><Pencil size={13} /></button><button onClick={() => props.onDeleteConversation(conversation.id)} aria-label="Excluir conversa"><Trash2 size={13} /></button></div>}
                </div>
              ))}
            </section>
          ))}
          {!filtered.length && <p className="sidebar-empty">Nenhuma conversa encontrada.</p>}
        </div>
      </div>

      {props.isAdmin && (
        <nav className="sidebar-admin" aria-label="Administração">
          <span>Admin</span>
          <button className={props.view === 'admin-overview' ? 'active' : ''} onClick={() => navigate('admin-overview')}><Activity size={17} /> Monitoramento</button>
          <button className={props.view === 'admin-model' ? 'active' : ''} onClick={() => navigate('admin-model')}><Cpu size={17} /> Modelo</button>
          <button className={props.view === 'admin-ai' ? 'active' : ''} onClick={() => navigate('admin-ai')}><ShieldCheck size={17} /> Configurações da IA</button>
        </nav>
      )}

      <div className="profile-menu-wrap">
        {profileOpen && (
          <div className="profile-menu" role="menu">
            <button onClick={() => { navigate('settings-profile'); setProfileOpen(false) }}><UserAvatar name={props.profile.displayName} src={props.profile.avatarDataUrl} size="small" /> Perfil</button>
            <button onClick={() => { navigate('settings-appearance'); setProfileOpen(false) }}><Settings size={15} /> Preferências</button>
            <button className="danger" onClick={props.onLogout}><LogOut size={15} /> Sair</button>
          </div>
        )}
        <button className="profile-trigger" onClick={() => setProfileOpen((value) => !value)} aria-expanded={profileOpen}>
          <UserAvatar name={props.profile.displayName} src={props.profile.avatarDataUrl} />
          <span><strong>{props.profile.displayName}</strong><small>{props.user.email}</small></span>
          <MoreHorizontal size={17} />
        </button>
      </div>
    </aside>
  )
}

