import { LoaderCircle, RefreshCw } from 'lucide-react'
import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import AuthScreen, { type AuthPayload, type AuthUser } from './AuthScreen'
import { apiUrl } from './api'
import AssistantWelcome from './components/assistant/AssistantWelcome'
import ChatView from './components/chat/ChatView'
import AdminPage from './components/pages/AdminPage'
import HistoryPage from './components/pages/HistoryPage'
import SettingsPage from './components/pages/SettingsPage'
import { AnalysesPage, MemoryPage } from './components/pages/WorkspacePages'
import Sidebar from './components/sidebar/Sidebar'
import Brand from './components/ui/Brand'
import { DEFAULT_SETTINGS } from './config/aiPresets'
import { useViewNavigation } from './lib/useViewNavigation'
import { cloudRequest, fetchCloudConversation, fetchCloudHistory, mergeCloudHistory, migrateLocalHistory } from './lib/cloudConversations'
import { createConversation, loadConversations, loadLastAssistant, loadProfile, loadSettings, loadUsage, pruneConversationHistory, saveConversations, saveLastAssistant, saveProfile, saveSettings, saveUsage } from './lib/storage'
import type { AssistantMode, AvailableModel, ChatMessage, Conversation, Health, LocalProfile, MessageFeedback, Usage, UsageRecord, UserSettings } from './types'

const AUTH_TOKEN_KEY = 'maua-ai-auth-token'

function App() {
  const initialConversation = useMemo(() => createConversation(), [])
  const [conversations, setConversations] = useState<Conversation[]>([initialConversation])
  const [activeId, setActiveId] = useState(initialConversation.id)
  const { view, navigate, goBack } = useViewNavigation()
  const [token, setToken] = useState(() => sessionStorage.getItem(AUTH_TOKEN_KEY) ?? '')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authReady, setAuthReady] = useState(() => !sessionStorage.getItem(AUTH_TOKEN_KEY))
  const [profile, setProfile] = useState<LocalProfile>({ displayName: '', avatarDataUrl: null })
  const [settings, setSettings] = useState<UserSettings>({ ...DEFAULT_SETTINGS })
  const [usageRecords, setUsageRecords] = useState<UsageRecord[]>([])
  const [health, setHealth] = useState<Health | null>(null)
  const [models, setModels] = useState<AvailableModel[]>([])
  const [connectionError, setConnectionError] = useState(false)
  const [input, setInput] = useState('')
  const [latestUsage, setLatestUsage] = useState<Usage | null>(null)
  const [isStreaming, setIsStreaming] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [mobileOpen, setMobileOpen] = useState(false)
  const [assistantMode, setAssistantMode] = useState<AssistantMode>('cmob')
  const [needsAssistantChoice, setNeedsAssistantChoice] = useState(false)
  const [historyLoaded, setHistoryLoaded] = useState(false)
  const [syncError, setSyncError] = useState('')
  const [refreshKey, setRefreshKey] = useState(0)
  const authTokenRef = useRef(token)
  const abortRef = useRef<AbortController | null>(null)

  const activeConversation = useMemo(() => conversations.find((item) => item.id === activeId) ?? conversations[0], [activeId, conversations])
  const assistantConversations = useMemo(() => conversations.filter((item) => item.assistantMode === assistantMode), [assistantMode, conversations])
  const isAdmin = user?.role?.toLocaleLowerCase('pt-BR') === 'admin'

  function initializeUser(authenticatedUser: AuthUser) {
    setHistoryLoaded(false)
    setSyncError('')
    let savedConversations = loadConversations(authenticatedUser.id)
    const savedSettings = loadSettings(authenticatedUser.id)
    const lastAssistant = loadLastAssistant(authenticatedUser.id)
    const initialMode = savedSettings.defaultAssistant === 'last' ? (lastAssistant ?? 'cmob') : savedSettings.defaultAssistant
    let initialConversation = savedConversations.find((conversation) => conversation.assistantMode === initialMode)
    if (!initialConversation) {
      initialConversation = createConversation(initialMode)
      savedConversations = [initialConversation, ...savedConversations]
    }
    setUser(authenticatedUser)
    setConversations(savedConversations)
    setActiveId(initialConversation.id)
    setAssistantMode(initialMode)
    setNeedsAssistantChoice(savedSettings.defaultAssistant === 'last' && lastAssistant === null)
    setProfile(loadProfile(authenticatedUser.id, authenticatedUser.name))
    setSettings(savedSettings)
    setUsageRecords(loadUsage(authenticatedUser.id))
  }

  useEffect(() => {
    fetch(apiUrl('/api/health'))
      .then((response) => {
        if (!response.ok) throw new Error('Backend indisponível')
        return response.json() as Promise<Health>
      })
      .then((data) => { setHealth(data); setConnectionError(false) })
      .catch(() => setConnectionError(true))
  }, [])

  useEffect(() => {
    if (!token) return
    const controller = new AbortController()
    fetch(apiUrl('/api/auth/me'), { headers: { Authorization: `Bearer ${token}` }, signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error('Sessão expirada')
        return response.json() as Promise<AuthUser>
      })
      .then((authenticatedUser) => { if (!controller.signal.aborted) initializeUser(authenticatedUser) })
      .catch(() => {
        if (controller.signal.aborted) return
        sessionStorage.removeItem(AUTH_TOKEN_KEY)
        authTokenRef.current = ''
        setToken('')
        setUser(null)
      })
      .finally(() => { if (!controller.signal.aborted) setAuthReady(true) })
    return () => controller.abort()
  }, [token])

  useEffect(() => {
    if (!token) return
    fetch(apiUrl('/api/models'), { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => response.ok ? response.json() : Promise.reject(new Error('Lista indisponível')))
      .then((payload: { data?: AvailableModel[] } | AvailableModel[]) => setModels(Array.isArray(payload) ? payload : payload.data ?? []))
      .catch(() => setModels([]))
  }, [token])

  useEffect(() => {
    if (!user || !historyLoaded) return
    try { saveConversations(user.id, conversations) } catch { /* Mantém a sessão mesmo se o armazenamento estiver cheio. */ }
  }, [conversations, user, historyLoaded])

  useEffect(() => {
    if (!user || !token || isStreaming) return
    const controller = new AbortController()
    let busy = false
    async function refresh() {
      if (busy || document.visibilityState === 'hidden') return
      busy = true
      try {
        await migrateLocalHistory(token, user!.id, loadConversations(user!.id), controller.signal)
        const remote = await fetchCloudHistory(token, controller.signal)
        if (controller.signal.aborted) return
        setConversations((current) => {
          let merged = mergeCloudHistory(remote, current)
          if (!merged.some((item) => item.assistantMode === assistantMode)) merged = [...merged, createConversation(assistantMode)]
          setActiveId((id) => merged.some((item) => item.id === id) ? id : merged.find((item) => item.assistantMode === assistantMode)!.id)
          return merged
        })
        setHistoryLoaded(true)
        setSyncError('')
        if (remote.length && loadLastAssistant(user!.id) === null && loadSettings(user!.id).defaultAssistant === 'last') {
          setAssistantMode(remote[0].assistantMode)
          setActiveId(remote[0].id)
          saveLastAssistant(user!.id, remote[0].assistantMode)
          setNeedsAssistantChoice(false)
        }
      } catch (error) {
        if (!controller.signal.aborted) setSyncError(error instanceof Error ? error.message : 'Nao foi possivel carregar o historico da conta.')
      } finally { busy = false }
    }
    void refresh()
    const handleRefresh = () => { void refresh() }
    const interval = window.setInterval(handleRefresh, 30_000)
    window.addEventListener('focus', handleRefresh)
    document.addEventListener('visibilitychange', handleRefresh)
    return () => {
      controller.abort()
      window.clearInterval(interval)
      window.removeEventListener('focus', handleRefresh)
      document.removeEventListener('visibilitychange', handleRefresh)
    }
  }, [user, token, isStreaming, assistantMode, refreshKey])

  useEffect(() => {
    if (!user) return
    try { saveSettings(user.id, settings) } catch { /* Preferências continuam válidas durante esta sessão. */ }
  }, [settings, user])

  useEffect(() => {
    if (!user) return
    try { saveProfile(user.id, profile) } catch { /* O perfil autenticado continua disponível. */ }
  }, [profile, user])

  useEffect(() => {
    if (!user) return
    try { saveUsage(user.id, usageRecords) } catch { /* Métricas locais são opcionais. */ }
  }, [usageRecords, user])

  useEffect(() => {
    document.documentElement.dataset.theme = settings.theme
    document.documentElement.dataset.density = settings.density
    document.documentElement.dataset.chatFont = settings.chatFontSize
  }, [settings.theme, settings.density, settings.chatFontSize])

  function back() {
    setMobileOpen(false)
    if (goBack()) return
    if (view !== 'chat') navigate('chat', true)
    else setNeedsAssistantChoice(true)
  }

  function updateConversation(id: string, updater: (conversation: Conversation) => Conversation) {
    setConversations((current) => current.map((conversation) => conversation.id === id ? updater(conversation) : conversation))
  }

  function newConversation() {
    abortRef.current?.abort()
    const conversation = createConversation(assistantMode)
    setConversations((current) => [conversation, ...current])
    setActiveId(conversation.id)
    setInput('')
    setLatestUsage(null)
    setMobileOpen(false)
    navigate('chat')
  }

  function selectConversation(id: string) {
    const selected = conversations.find((conversation) => conversation.id === id)
    if (selected && selected.assistantMode !== assistantMode) {
      setAssistantMode(selected.assistantMode)
      if (user) saveLastAssistant(user.id, selected.assistantMode)
    }
    setActiveId(id)
    setMobileOpen(false)
    setLatestUsage(null)
    navigate('chat')
  }

  async function deleteConversation(id: string) {
    if (!window.confirm('Excluir esta conversa da sua conta em todos os dispositivos?')) return
    abortRef.current?.abort()
    const selected = conversations.find((item) => item.id === id)
    try {
      if (selected?.cloud) await cloudRequest(token, `/api/conversations/${encodeURIComponent(id)}`, 'DELETE')
      if (authTokenRef.current !== token) return
    } catch (error) { setSyncError(error instanceof Error ? error.message : 'Falha ao excluir conversa.'); return }
    setConversations((current) => {
      const remaining = current.filter((conversation) => conversation.id !== id)
      if (id !== activeId) return remaining
      const sameAssistant = remaining.filter((conversation) => conversation.assistantMode === assistantMode)
      if (sameAssistant.length) {
        setActiveId(sameAssistant[0].id)
        return remaining
      }
      const fresh = createConversation(assistantMode)
      setActiveId(fresh.id)
      return [fresh, ...remaining]
    })
  }

  function switchAssistant(mode: AssistantMode) {
    abortRef.current?.abort()
    setAssistantMode(mode)
    setNeedsAssistantChoice(false)
    if (user) saveLastAssistant(user.id, mode)
    const existing = conversations
      .filter((conversation) => conversation.assistantMode === mode)
      .sort((a, b) => b.updatedAt - a.updatedAt)[0]
    if (existing) {
      setActiveId(existing.id)
    } else {
      const fresh = createConversation(mode)
      setConversations((current) => [fresh, ...current])
      setActiveId(fresh.id)
    }
    setInput('')
    setLatestUsage(null)
    setMobileOpen(false)
    navigate('chat')
  }

  async function renameConversation(id: string, title: string) {
    const selected = conversations.find((item) => item.id === id)
    try {
      if (selected?.cloud) await cloudRequest(token, `/api/conversations/${encodeURIComponent(id)}`, 'PATCH', { title: title.slice(0, 80) })
      if (authTokenRef.current !== token) return
    } catch (error) { setSyncError(error instanceof Error ? error.message : 'Falha ao renomear conversa.'); return }
    updateConversation(id, (conversation) => ({ ...conversation, title: title.slice(0, 80), updatedAt: Date.now() }))
  }

  async function clearConversation() {
    if (!activeConversation || !window.confirm('Limpar todas as mensagens desta conversa?')) return
    abortRef.current?.abort()
    try {
      if (activeConversation.cloud) await cloudRequest(token, `/api/conversations/${encodeURIComponent(activeConversation.id)}/clear`, 'POST')
      if (authTokenRef.current !== token) return
    } catch (error) { setSyncError(error instanceof Error ? error.message : 'Falha ao limpar conversa.'); return }
    updateConversation(activeConversation.id, (conversation) => ({ ...conversation, messages: [], title: 'Nova conversa', updatedAt: Date.now() }))
    setLatestUsage(null)
  }

  async function sendMessage(prefilled?: string, regenerateAssistantId?: string) {
    if (!activeConversation || isStreaming || !historyLoaded) return
    const current = activeConversation
    let content = (prefilled ?? input).trim()
    let requestMessages: ChatMessage[]
    let assistantId: string = crypto.randomUUID()
    const now = Date.now()

    if (!current.cloud && content && !regenerateAssistantId) {
      setIsStreaming(true)
      try {
        await cloudRequest(token, '/api/conversations', 'POST', { id: current.id, title: content.slice(0, 56), assistant_mode: current.assistantMode })
        if (authTokenRef.current !== token) return
        updateConversation(current.id, (item) => ({ ...item, cloud: true }))
      } catch (error) {
        if (authTokenRef.current === token) { setSyncError(error instanceof Error ? error.message : 'Falha ao salvar conversa.'); setIsStreaming(false) }
        return
      }
    }

    if (regenerateAssistantId) {
      const assistantIndex = current.messages.findIndex((message) => message.id === regenerateAssistantId)
      if (assistantIndex < 1) return
      const userMessage = [...current.messages.slice(0, assistantIndex)].reverse().find((message) => message.role === 'user')
      if (!userMessage) return
      setIsStreaming(true)
      try {
        const lastId = current.messages.at(-1)?.id ?? ''
        if (!userMessage.id.startsWith('server-') || !lastId.startsWith('server-')) throw new Error('Recarregue o historico antes de gerar novamente.')
        await cloudRequest(token, `/api/conversations/${encodeURIComponent(current.id)}/rewind`, 'POST', {
          message_id: Number(userMessage.id.slice(7)), last_message_id: Number(lastId.slice(7)),
        })
        if (authTokenRef.current !== token) return
      } catch (error) {
        if (authTokenRef.current === token) { setSyncError(error instanceof Error ? error.message : 'Falha ao gerar novamente.'); setIsStreaming(false); setRefreshKey((key) => key + 1) }
        return
      }
      content = userMessage.content
      assistantId = regenerateAssistantId
      requestMessages = current.messages.slice(0, assistantIndex).filter((message) => !message.error)
      updateConversation(current.id, (conversation) => ({ ...conversation, messages: [...conversation.messages.slice(0, assistantIndex), { id: assistantId, role: 'assistant', content: '', reasoning: '', pending: true, createdAt: now }], updatedAt: now }))
    } else {
      if (!content) return
      const userMessage: ChatMessage = { id: crypto.randomUUID(), role: 'user', content, createdAt: now }
      const assistantMessage: ChatMessage = { id: assistantId, role: 'assistant', content: '', reasoning: '', pending: true, createdAt: now }
      requestMessages = [...current.messages.filter((message) => !message.error), userMessage]
      updateConversation(current.id, (conversation) => ({ ...conversation, title: conversation.messages.length === 0 ? content.slice(0, 56) : conversation.title, messages: [...conversation.messages, userMessage, assistantMessage], updatedAt: now }))
    }

    setInput('')
    setLatestUsage(null)
    setIsStreaming(true)
    const controller = new AbortController()
    abortRef.current = controller
    const startedAt = performance.now()
    let firstTokenAt: number | undefined
    let answer = ''
    let reasoning = ''
    let responseUsage: Usage | undefined
    let requestStatus: UsageRecord['status'] = 'success'

    const patchAssistant = (patch: Partial<ChatMessage>) => {
      if (authTokenRef.current === token) updateConversation(current.id, (conversation) => ({ ...conversation, messages: conversation.messages.map((message) => message.id === assistantId ? { ...message, ...patch } : message), updatedAt: Date.now() }))
    }

    function processEvent(line: string) {
      if (!line.trim()) return
      const event = JSON.parse(line) as { type: 'delta' | 'reasoning' | 'usage' | 'done' | 'error'; content?: string; message?: string; usage?: Usage }
      if (event.type === 'delta') {
        if (firstTokenAt === undefined) firstTokenAt = performance.now()
        answer += event.content ?? ''
        if (settings.streaming) patchAssistant({ content: answer })
      } else if (event.type === 'reasoning') {
        reasoning += event.content ?? ''
        if (settings.streaming) patchAssistant({ reasoning })
      } else if (event.type === 'usage' && event.usage) {
        responseUsage = event.usage
        setLatestUsage(event.usage)
      } else if (event.type === 'error') throw new Error(event.message ?? 'O servidor interrompeu a resposta.')
    }

    try {
      const recentMessages = pruneConversationHistory([{ ...current, messages: requestMessages }])[0]?.messages ?? []
      if (!recentMessages.length) throw new Error('Estas mensagens expiraram. Atualize o historico antes de continuar.')
      const response = await fetch(apiUrl('/api/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        signal: controller.signal,
        body: JSON.stringify({ messages: recentMessages.slice(-40).map(({ role, content: messageContent }) => ({ role, content: messageContent })), temperature: settings.temperature, max_tokens: settings.maxTokens, thinking: Boolean(health?.supports_thinking && settings.thinking), conversation_id: current.id, assistant: current.assistantMode }),
      })
      if (!response.ok) {
        const payload = await response.json().catch(() => null) as { detail?: string } | null
        throw new Error(payload?.detail ?? `Falha na requisição (HTTP ${response.status}).`)
      }
      if (!response.body) throw new Error('O navegador não recebeu o fluxo de resposta.')
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''
        lines.forEach(processEvent)
        if (done) break
      }
      processEvent(buffer)
      if (!answer.trim()) throw new Error('O modelo retornou uma resposta vazia. Tente novamente.')
      const durationMs = performance.now() - startedAt
      patchAssistant({ content: answer, reasoning, pending: false, usage: responseUsage, durationMs, ttftMs: firstTokenAt ? firstTokenAt - startedAt : undefined })
      try {
        const saved = await fetchCloudConversation(token, current.id, controller.signal)
        if (authTokenRef.current === token) updateConversation(current.id, (item) => mergeCloudHistory([saved], [item])[0])
      } catch (error) {
        if (!controller.signal.aborted && authTokenRef.current === token) setSyncError(error instanceof Error ? error.message : 'Falha ao atualizar o historico.')
      }
    } catch (error) {
      const aborted = controller.signal.aborted
      requestStatus = aborted ? 'cancelled' : 'error'
      const errorMessage = aborted ? (answer || 'Resposta interrompida.') : error instanceof Error ? error.message : 'Não foi possível gerar a resposta.'
      patchAssistant({ content: errorMessage, reasoning, pending: false, error: !aborted })
    } finally {
      if (authTokenRef.current === token) {
        const durationMs = performance.now() - startedAt
        setUsageRecords((records) => [...records, { id: crypto.randomUUID(), timestamp: Date.now(), conversationId: current.id, assistantMode: current.assistantMode, usage: responseUsage, durationMs, ttftMs: firstTokenAt ? firstTokenAt - startedAt : undefined, status: requestStatus }].slice(-500))
        setIsStreaming(false)
        abortRef.current = null
      }
    }
  }

  async function copyMessage(message: ChatMessage) {
    await navigator.clipboard.writeText(message.content)
    setCopiedId(message.id)
    window.setTimeout(() => setCopiedId(null), 1500)
  }

  function feedback(messageId: string, value: MessageFeedback) {
    updateConversation(activeId, (conversation) => ({ ...conversation, messages: conversation.messages.map((message) => message.id === messageId ? { ...message, feedback: value } : message) }))
  }

  function authenticated(payload: AuthPayload) {
    sessionStorage.setItem(AUTH_TOKEN_KEY, payload.access_token)
    authTokenRef.current = payload.access_token
    setAuthReady(false)
    setUser(null)
    setToken(payload.access_token)
  }

  function logout() {
    abortRef.current?.abort()
    sessionStorage.removeItem(AUTH_TOKEN_KEY)
    setToken('')
    authTokenRef.current = ''
    setHistoryLoaded(false)
    setIsStreaming(false)
    setUser(null)
    navigate('chat')
  }

  if (!authReady) return <div className="app-loading"><Brand /><LoaderCircle className="spin" size={21} /></div>
  if (!user || !token) return <AuthScreen onAuthenticated={authenticated} />
  if (!historyLoaded && !syncError) return <div className="app-loading"><Brand /><LoaderCircle className="spin" size={21} /></div>
  if (needsAssistantChoice) return <AssistantWelcome onSelect={switchAssistant} />

  let content: ReactNode
  const navigation = { onBack: back, onOpenMenu: () => setMobileOpen(true) }
  if (view === 'chat') content = <ChatView {...navigation} conversation={activeConversation} user={user} profile={profile} health={health} models={models} connectionError={connectionError} input={input} usage={latestUsage} settings={settings} isStreaming={isStreaming} copiedId={copiedId} assistantMode={assistantMode} onInput={setInput} onSend={(value) => void sendMessage(value)} onStop={() => abortRef.current?.abort()} onCopy={(message) => void copyMessage(message)} onRegenerate={(id) => void sendMessage(undefined, id)} onFeedback={feedback} onClear={clearConversation} onAssistantChange={switchAssistant} />
  else if (view === 'history') content = <HistoryPage {...navigation} conversations={conversations} assistantMode={assistantMode} settings={settings} onOpen={selectConversation} onDelete={deleteConversation} onRename={renameConversation} />
  else if (view === 'analyses') content = <AnalysesPage {...navigation} conversations={assistantConversations} onOpen={selectConversation} />
  else if (view === 'memory') content = <MemoryPage {...navigation} conversations={assistantConversations} />
  else if (view.startsWith('settings-')) content = <SettingsPage {...navigation} view={view} user={user} profile={profile} settings={settings} health={health} onNavigate={navigate} onProfile={setProfile} onSettings={setSettings} />
  else content = <AdminPage {...navigation} view={view} isAdmin={isAdmin} health={health} models={models} usageRecords={usageRecords} settings={settings} onSettings={setSettings} />

  return <div className={`app-shell-v2 assistant-${assistantMode}`}>{mobileOpen && <button className="sidebar-scrim" onClick={() => setMobileOpen(false)} aria-label="Fechar menu" />}<Sidebar view={view} conversations={assistantConversations} activeId={activeId} user={user} profile={profile} isAdmin={isAdmin} mobileOpen={mobileOpen} assistantMode={assistantMode} onCloseMobile={() => setMobileOpen(false)} onNavigate={navigate} onNewChat={newConversation} onSelectConversation={selectConversation} onDeleteConversation={deleteConversation} onRenameConversation={renameConversation} onLogout={logout} /><div className="cloud-workspace">{syncError && <div className="history-sync-error" role="alert"><span>{syncError}</span><button className="icon-button" title="Tentar sincronizar novamente" aria-label="Tentar sincronizar novamente" onClick={() => setRefreshKey((key) => key + 1)}><RefreshCw size={17} /></button></div>}{content}</div></div>
}

export default App
