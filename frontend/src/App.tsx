import { useEffect, useMemo, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AlertTriangle,
  BookOpen,
  BrainCircuit,
  Check,
  ChevronDown,
  Clipboard,
  Code2,
  GraduationCap,
  LoaderCircle,
  LogOut,
  Menu,
  MessageSquareText,
  Plus,
  Send,
  Settings2,
  Sparkles,
  Square,
  Trash2,
  X,
} from 'lucide-react'
import AuthScreen, { type AuthPayload, type AuthUser } from './AuthScreen'
import { apiUrl } from './api'

type Role = 'user' | 'assistant'

type ChatMessage = {
  id: string
  role: Role
  content: string
  reasoning?: string
  pending?: boolean
  error?: boolean
}

type Conversation = {
  id: string
  title: string
  messages: ChatMessage[]
  updatedAt: number
}

type Health = {
  status: string
  configured: boolean
  database_ready: boolean
  model: string
}

type Usage = {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
}

const STORAGE_KEY = 'maua-ai-conversations-v1'
const SETTINGS_KEY = 'maua-ai-settings-v1'
const AUTH_TOKEN_KEY = 'maua-ai-auth-token'

const suggestions = [
  {
    icon: BookOpen,
    title: 'Resumir um assunto',
    prompt: 'Faça um resumo claro sobre redes neurais, com os conceitos mais importantes.',
  },
  {
    icon: Code2,
    title: 'Revisar um código',
    prompt: 'Quais pontos devo observar ao revisar a qualidade de um código Python?',
  },
  {
    icon: GraduationCap,
    title: 'Planejar um trabalho',
    prompt: 'Monte uma estrutura de tópicos para um trabalho acadêmico sobre ética em IA.',
  },
]

function createConversation(): Conversation {
  return {
    id: crypto.randomUUID(),
    title: 'Nova conversa',
    messages: [],
    updatedAt: Date.now(),
  }
}

function loadConversations(userId: string): Conversation[] {
  try {
    const saved = localStorage.getItem(`${STORAGE_KEY}:${userId}`)
    if (saved) {
      const parsed = JSON.parse(saved) as Conversation[]
      if (Array.isArray(parsed) && parsed.length) return parsed
    }
  } catch {
    // Se os dados locais estiverem inválidos, iniciamos uma conversa limpa.
  }
  return [createConversation()]
}

function loadSettings() {
  try {
    const saved = localStorage.getItem(SETTINGS_KEY)
    if (saved) return { temperature: 0.25, maxTokens: 1200, thinking: false, ...JSON.parse(saved) }
  } catch {
    // Usa os valores recomendados pela documentação da Mauá.
  }
  return { temperature: 0.25, maxTokens: 1200, thinking: false }
}

function App() {
  const [conversations, setConversations] = useState<Conversation[]>(() => [createConversation()])
  const [activeId, setActiveId] = useState(() => conversations[0].id)
  const [token, setToken] = useState(() => sessionStorage.getItem(AUTH_TOKEN_KEY) ?? '')
  const [user, setUser] = useState<AuthUser | null>(null)
  const [authReady, setAuthReady] = useState(() => !sessionStorage.getItem(AUTH_TOKEN_KEY))
  const [input, setInput] = useState('')
  const [health, setHealth] = useState<Health | null>(null)
  const [connectionError, setConnectionError] = useState(false)
  const [isStreaming, setIsStreaming] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [settingsOpen, setSettingsOpen] = useState(false)
  const [copiedId, setCopiedId] = useState<string | null>(null)
  const [usage, setUsage] = useState<Usage | null>(null)
  const [settings, setSettings] = useState(loadSettings)
  const abortRef = useRef<AbortController | null>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const endRef = useRef<HTMLDivElement>(null)

  const activeConversation = useMemo(
    () => conversations.find((conversation) => conversation.id === activeId) ?? conversations[0],
    [activeId, conversations],
  )

  useEffect(() => {
    if (!user) return
    try {
      localStorage.setItem(`${STORAGE_KEY}:${user.id}`, JSON.stringify(conversations))
    } catch {
      // O chat continua funcionando se o limite de armazenamento do navegador for atingido.
    }
  }, [conversations, user])

  useEffect(() => {
    if (!token) return
    fetch(apiUrl('/api/auth/me'), { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (!response.ok) throw new Error('Sessão expirada')
        return response.json() as Promise<AuthUser>
      })
      .then((authenticatedUser) => {
        const savedConversations = loadConversations(authenticatedUser.id)
        setUser(authenticatedUser)
        setConversations(savedConversations)
        setActiveId(savedConversations[0].id)
      })
      .catch(() => {
        sessionStorage.removeItem(AUTH_TOKEN_KEY)
        setToken('')
      })
      .finally(() => setAuthReady(true))
  }, [token])

  useEffect(() => {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings))
    } catch {
      // Mantém os ajustes apenas na sessão atual se o armazenamento não estiver disponível.
    }
  }, [settings])

  useEffect(() => {
    fetch(apiUrl('/api/health'))
      .then((response) => {
        if (!response.ok) throw new Error('Backend indisponível')
        return response.json() as Promise<Health>
      })
      .then((data) => setHealth(data))
      .catch(() => setConnectionError(true))
  }, [])

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: isStreaming ? 'auto' : 'smooth' })
  }, [activeConversation.messages, isStreaming])

  function updateConversation(id: string, updater: (conversation: Conversation) => Conversation) {
    setConversations((current) => current.map((item) => (item.id === id ? updater(item) : item)))
  }

  function newConversation() {
    if (isStreaming) abortRef.current?.abort()
    const conversation = createConversation()
    setConversations((current) => [conversation, ...current])
    setActiveId(conversation.id)
    setInput('')
    setUsage(null)
    setSidebarOpen(false)
    requestAnimationFrame(() => textareaRef.current?.focus())
  }

  function deleteConversation(id: string) {
    const remaining = conversations.filter((conversation) => conversation.id !== id)
    if (!remaining.length) {
      const fresh = createConversation()
      setConversations([fresh])
      setActiveId(fresh.id)
    } else {
      setConversations(remaining)
      if (id === activeId) setActiveId(remaining[0].id)
    }
  }

  function resizeTextarea() {
    const element = textareaRef.current
    if (!element) return
    element.style.height = 'auto'
    element.style.height = `${Math.min(element.scrollHeight, 180)}px`
  }

  async function sendMessage(prefilled?: string) {
    const content = (prefilled ?? input).trim()
    if (!content || isStreaming || !activeConversation) return

    if (!health?.configured) {
      setInput(content)
      return
    }

    const conversationId = activeConversation.id
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
    }
    const assistantId = crypto.randomUUID()
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      reasoning: '',
      pending: true,
    }
    // Limita o histórico enviado para evitar gastar a janela de contexto em conversas longas.
    const history = [...activeConversation.messages.filter((message) => !message.error), userMessage].slice(-40)

    updateConversation(conversationId, (conversation) => ({
      ...conversation,
      title: conversation.messages.length === 0 ? content.slice(0, 48) : conversation.title,
      messages: [...conversation.messages, userMessage, assistantMessage],
      updatedAt: Date.now(),
    }))
    setInput('')
    setUsage(null)
    setIsStreaming(true)
    if (textareaRef.current) textareaRef.current.style.height = 'auto'

    const controller = new AbortController()
    abortRef.current = controller

    const patchAssistant = (patch: Partial<ChatMessage>) => {
      updateConversation(conversationId, (conversation) => ({
        ...conversation,
        messages: conversation.messages.map((message) =>
          message.id === assistantId ? { ...message, ...patch } : message,
        ),
        updatedAt: Date.now(),
      }))
    }

    try {
      const response = await fetch(apiUrl('/api/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        signal: controller.signal,
        body: JSON.stringify({
          messages: [
            {
              role: 'system',
              content:
                'Você é um assistente acadêmico prestativo. Responda em português do Brasil, com clareza, precisão e honestidade. Não invente fontes.',
            },
            ...history.map(({ role, content: messageContent }) => ({ role, content: messageContent })),
          ],
          temperature: settings.temperature,
          max_tokens: settings.maxTokens,
          thinking: settings.thinking,
        }),
      })

      if (!response.ok) {
        const error = (await response.json().catch(() => null)) as { detail?: string } | null
        throw new Error(error?.detail ?? `Falha na requisição (HTTP ${response.status}).`)
      }
      if (!response.body) throw new Error('O navegador não recebeu o fluxo de resposta.')

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let answer = ''
      let reasoning = ''

      while (true) {
        const { value, done } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        const lines = buffer.split('\n')
        buffer = lines.pop() ?? ''

        for (const line of lines) {
          if (!line.trim()) continue
          const event = JSON.parse(line) as {
            type: 'delta' | 'reasoning' | 'usage' | 'done' | 'error'
            content?: string
            message?: string
            usage?: Usage
          }
          if (event.type === 'delta') {
            answer += event.content ?? ''
            patchAssistant({ content: answer })
          } else if (event.type === 'reasoning') {
            reasoning += event.content ?? ''
            patchAssistant({ reasoning })
          } else if (event.type === 'usage' && event.usage) {
            setUsage(event.usage)
          } else if (event.type === 'error') {
            throw new Error(event.message ?? 'O servidor interrompeu a resposta.')
          }
        }
        if (done) break
      }

      if (!answer.trim()) {
        throw new Error('O modelo retornou uma resposta vazia. Tente uma conversa nova ou reduza o histórico.')
      }
      patchAssistant({ pending: false })
    } catch (error) {
      if (controller.signal.aborted) {
        patchAssistant({ pending: false, content: 'Resposta interrompida.' })
      } else {
        const message = error instanceof Error ? error.message : 'Não foi possível gerar a resposta.'
        patchAssistant({ pending: false, error: true, content: message })
      }
    } finally {
      setIsStreaming(false)
      abortRef.current = null
    }
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      void sendMessage()
    }
  }

  async function copyMessage(message: ChatMessage) {
    await navigator.clipboard.writeText(message.content)
    setCopiedId(message.id)
    window.setTimeout(() => setCopiedId(null), 1600)
  }

  function authenticated(payload: AuthPayload) {
    sessionStorage.setItem(AUTH_TOKEN_KEY, payload.access_token)
    const savedConversations = loadConversations(payload.user.id)
    setToken(payload.access_token)
    setUser(payload.user)
    setConversations(savedConversations)
    setActiveId(savedConversations[0].id)
  }

  function logout() {
    abortRef.current?.abort()
    sessionStorage.removeItem(AUTH_TOKEN_KEY)
    setToken('')
    setUser(null)
    const fresh = createConversation()
    setConversations([fresh])
    setActiveId(fresh.id)
  }

  const notReady = connectionError || (health && !health.configured)

  if (!authReady) {
    return <div className="auth-loading"><div className="brand-mark"><Sparkles size={20} /></div><LoaderCircle className="spin" size={22} /></div>
  }

  if (!user || !token) return <AuthScreen onAuthenticated={authenticated} />

  return (
    <div className="app-shell">
      {sidebarOpen && <button className="sidebar-scrim" onClick={() => setSidebarOpen(false)} aria-label="Fechar menu" />}

      <aside className={`sidebar ${sidebarOpen ? 'is-open' : ''}`}>
        <div className="brand-row">
          <div className="brand-mark"><Sparkles size={19} strokeWidth={2.2} /></div>
          <div>
            <div className="brand-name">Mauá <span>AI</span></div>
            <div className="brand-caption">Assistente acadêmico</div>
          </div>
          <button className="icon-button sidebar-close" onClick={() => setSidebarOpen(false)} aria-label="Fechar menu"><X size={19} /></button>
        </div>

        <button className="new-chat" onClick={newConversation}>
          <Plus size={18} /> Nova conversa
        </button>

        <div className="history-label">Conversas recentes</div>
        <nav className="history-list" aria-label="Conversas recentes">
          {[...conversations]
            .sort((a, b) => b.updatedAt - a.updatedAt)
            .map((conversation) => (
              <div className={`history-item ${conversation.id === activeId ? 'active' : ''}`} key={conversation.id}>
                <button
                  className="history-select"
                  onClick={() => {
                    setActiveId(conversation.id)
                    setSidebarOpen(false)
                  }}
                >
                  <MessageSquareText size={16} />
                  <span>{conversation.title}</span>
                </button>
                <button className="history-delete" onClick={() => deleteConversation(conversation.id)} aria-label="Excluir conversa">
                  <Trash2 size={15} />
                </button>
              </div>
            ))}
        </nav>

        <div className="sidebar-footer">
          <button className="settings-button" onClick={() => setSettingsOpen((open) => !open)}>
            <Settings2 size={17} /> Ajustes da resposta <ChevronDown size={15} className={settingsOpen ? 'rotate' : ''} />
          </button>
          {settingsOpen && (
            <div className="settings-panel">
              <label>
                <span>Temperatura <strong>{settings.temperature.toFixed(2)}</strong></span>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={settings.temperature}
                  onChange={(event) => setSettings({ ...settings, temperature: Number(event.target.value) })}
                />
              </label>
              <label>
                <span>Limite da resposta</span>
                <select
                  value={settings.maxTokens}
                  onChange={(event) => setSettings({ ...settings, maxTokens: Number(event.target.value) })}
                >
                  <option value={600}>Curta · 600 tokens</option>
                  <option value={1200}>Média · 1.200 tokens</option>
                  <option value={2400}>Longa · 2.400 tokens</option>
                </select>
              </label>
              <label className="switch-row">
                <span><BrainCircuit size={15} /> Raciocínio profundo</span>
                <input
                  type="checkbox"
                  checked={settings.thinking}
                  onChange={(event) => setSettings({ ...settings, thinking: event.target.checked })}
                />
              </label>
              <p>O modo rápido é recomendado para poupar contexto.</p>
            </div>
          )}
          <div className="privacy-note">
            <span className="privacy-dot" /> Histórico salvo somente neste navegador
          </div>
          <div className="user-card">
            <div className="user-avatar">{user.name.charAt(0).toUpperCase()}</div>
            <div><strong>{user.name}</strong><span>{user.email}</span></div>
            <button onClick={logout} aria-label="Sair da conta" title="Sair"><LogOut size={16} /></button>
          </div>
        </div>
      </aside>

      <main className="chat-area">
        <header className="topbar">
          <button className="icon-button menu-button" onClick={() => setSidebarOpen(true)} aria-label="Abrir menu"><Menu size={21} /></button>
          <div className="model-info">
            <span className="model-name">{health?.model ?? 'qwen/qwen3.8-27b'}</span>
            <span className={`status-pill ${notReady ? 'offline' : ''}`}>
              <span /> {connectionError ? 'Backend offline' : health?.configured ? 'Servidor Mauá' : health ? 'Configuração pendente' : 'Verificando'}
            </span>
          </div>
          <div className="topbar-wordmark">Instituto Mauá de Tecnologia</div>
        </header>

        <section className={`messages ${activeConversation.messages.length === 0 ? 'empty' : ''}`}>
          {activeConversation.messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-orbit"><Sparkles size={29} /></div>
              <p className="eyebrow">IA LOCAL · AMBIENTE ACADÊMICO</p>
              <h1>Como posso ajudar<br />no seu projeto?</h1>
              <p className="welcome-copy">Converse com o modelo da Mauá para estudar, programar, explorar ideias e desenvolver seus trabalhos.</p>

              {notReady && (
                <div className="setup-alert">
                  <AlertTriangle size={20} />
                  <div>
                    <strong>{connectionError ? 'O backend não está rodando' : 'Só falta conectar o servidor'}</strong>
                    <span>{connectionError ? 'Inicie a API Python na porta 8000.' : 'Copie .env.example para .env e informe a MAUA_AI_BASE_URL.'}</span>
                  </div>
                </div>
              )}

              <div className="suggestion-grid">
                {suggestions.map(({ icon: Icon, title, prompt }) => (
                  <button key={title} onClick={() => void sendMessage(prompt)} disabled={!health?.configured}>
                    <Icon size={19} />
                    <strong>{title}</strong>
                    <span>{prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="message-list">
              {activeConversation.messages.map((message) => (
                <article className={`message ${message.role} ${message.error ? 'error' : ''}`} key={message.id}>
                  <div className="avatar">
                    {message.role === 'assistant' ? <Sparkles size={17} /> : user.name.charAt(0).toUpperCase()}
                  </div>
                  <div className="message-body">
                    <div className="message-author">{message.role === 'assistant' ? 'Mauá AI' : 'Você'}</div>
                    {message.reasoning && (
                      <details className="reasoning">
                        <summary>Ver raciocínio</summary>
                        <p>{message.reasoning}</p>
                      </details>
                    )}
                    <div className="message-content">
                      {message.pending && !message.content ? (
                        <div className="thinking"><span /><span /><span /></div>
                      ) : message.role === 'assistant' ? (
                        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                      ) : (
                        <p>{message.content}</p>
                      )}
                      {message.pending && message.content && <span className="cursor" />}
                    </div>
                    {message.role === 'assistant' && message.content && !message.pending && !message.error && (
                      <button className="copy-button" onClick={() => void copyMessage(message)}>
                        {copiedId === message.id ? <Check size={14} /> : <Clipboard size={14} />}
                        {copiedId === message.id ? 'Copiado' : 'Copiar'}
                      </button>
                    )}
                  </div>
                </article>
              ))}
              <div ref={endRef} />
            </div>
          )}
        </section>

        <footer className="composer-wrap">
          {usage?.total_tokens && <div className="usage">Última resposta: {usage.total_tokens.toLocaleString('pt-BR')} tokens</div>}
          <div className={`composer ${isStreaming ? 'streaming' : ''}`}>
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => {
                setInput(event.target.value)
                resizeTextarea()
              }}
              onKeyDown={handleKeyDown}
              placeholder={health?.configured ? 'Pergunte alguma coisa…' : 'Configure a URL da API para começar…'}
              rows={1}
              disabled={!health?.configured || isStreaming}
              aria-label="Mensagem"
            />
            {isStreaming ? (
              <button className="send-button stop" onClick={() => abortRef.current?.abort()} aria-label="Interromper resposta"><Square size={15} fill="currentColor" /></button>
            ) : (
              <button className="send-button" onClick={() => void sendMessage()} disabled={!input.trim() || !health?.configured} aria-label="Enviar mensagem"><Send size={18} /></button>
            )}
          </div>
          <p className="disclaimer">A IA pode cometer erros. Confira informações importantes e cite fontes originais.</p>
        </footer>
      </main>
    </div>
  )
}

export default App
