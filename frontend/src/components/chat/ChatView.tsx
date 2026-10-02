import { useEffect, useRef } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  AlertTriangle,
  BarChart3,
  BusFront,
  Check,
  Clipboard,
  Menu,
  RotateCcw,
  Send,
  Square,
  ThumbsDown,
  ThumbsUp,
  Trash2,
  UsersRound,
  Waypoints,
} from 'lucide-react'
import type { AuthUser } from '../../AuthScreen'
import type { AvailableModel, ChatMessage, Conversation, Health, LocalProfile, MessageFeedback, Usage, UserSettings } from '../../types'
import ModelStatus from '../ai/ModelStatus'
import UserAvatar from '../ui/UserAvatar'

type Props = {
  conversation: Conversation
  user: AuthUser
  profile: LocalProfile
  health: Health | null
  models: AvailableModel[]
  connectionError: boolean
  input: string
  usage: Usage | null
  settings: UserSettings
  isStreaming: boolean
  copiedId: string | null
  onOpenMenu: () => void
  onInput: (value: string) => void
  onSend: (content?: string) => void
  onStop: () => void
  onCopy: (message: ChatMessage) => void
  onRegenerate: (messageId: string) => void
  onFeedback: (messageId: string, feedback: MessageFeedback) => void
  onClear: () => void
}

const suggestions = [
  { icon: UsersRound, label: 'Passageiros em agosto', prompt: 'Quantos passageiros pagantes e não pagantes tivemos em agosto?' },
  { icon: BarChart3, label: 'Comparar períodos', prompt: 'Compare as viagens realizadas em julho e agosto e destaque as principais variações.' },
  { icon: BusFront, label: 'Ranking de linhas', prompt: 'Quais linhas apresentaram mais viagens no período disponível?' },
  { icon: Waypoints, label: 'Cumprimento operacional', prompt: 'Analise o cumprimento das viagens e me dê os principais insights.' },
]

function formatTime(timestamp: number) {
  return new Intl.DateTimeFormat('pt-BR', { hour: '2-digit', minute: '2-digit' }).format(timestamp)
}

export default function ChatView(props: Props) {
  const endRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const ready = Boolean(props.health?.configured || props.health?.analytics_ready)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: props.isStreaming ? 'auto' : 'smooth' })
  }, [props.conversation.messages, props.isStreaming])

  function resize() {
    const textarea = textareaRef.current
    if (!textarea) return
    textarea.style.height = 'auto'
    textarea.style.height = `${Math.min(textarea.scrollHeight, 180)}px`
  }

  function submit() {
    props.onSend()
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  return (
    <main className="workspace chat-workspace">
      <header className="workspace-header chat-header">
        <button className="icon-button mobile-menu" onClick={props.onOpenMenu} aria-label="Abrir menu"><Menu size={20} /></button>
        <div className="header-title"><strong>{props.conversation.title}</strong><span>SEMOB · Assistente de mobilidade urbana</span></div>
        <div className="header-actions">
          {props.conversation.messages.length > 0 && <button className="icon-button" onClick={props.onClear} aria-label="Limpar conversa" title="Limpar conversa"><Trash2 size={17} /></button>}
          <ModelStatus health={props.health} models={props.models} connectionError={props.connectionError} />
        </div>
      </header>

      <section className={`chat-scroll ${props.conversation.messages.length === 0 ? 'is-empty' : ''}`}>
        {props.conversation.messages.length === 0 ? (
          <div className="chat-welcome">
            <div className="welcome-mark"><Waypoints size={25} /></div>
            <p className="section-kicker">SEMOB · cMob AI</p>
            <h1>Como posso ajudar na sua análise?</h1>
            <p>Converse com os dados de transporte e aprofunde comparações, tendências e indicadores operacionais.</p>
            {(!ready || props.connectionError) && (
              <div className="inline-alert" role="status">
                <AlertTriangle size={18} />
                <span><strong>{props.connectionError ? 'Backend indisponível.' : 'IA ainda não configurada.'}</strong> Verifique o serviço antes de enviar uma pergunta.</span>
              </div>
            )}
            <div className="prompt-grid">
              {suggestions.map(({ icon: Icon, label, prompt }) => (
                <button key={label} onClick={() => props.onSend(prompt)} disabled={!ready || props.isStreaming}>
                  <Icon size={18} /><span><strong>{label}</strong><small>{prompt}</small></span>
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="message-list-v2">
            {props.conversation.messages.map((message) => (
              <article className={`chat-message ${message.role} ${message.error ? 'has-error' : ''}`} key={message.id}>
                {message.role === 'assistant' ? <div className="assistant-avatar"><Waypoints size={16} /></div> : <UserAvatar name={props.profile.displayName} src={props.profile.avatarDataUrl} size="small" />}
                <div className="message-column">
                  <div className="message-heading">
                    <strong>{message.role === 'assistant' ? 'cMob AI' : props.profile.displayName}</strong>
                    {props.settings.showTimestamps && <time>{formatTime(message.createdAt)}</time>}
                  </div>
                  {message.reasoning && (
                    <details className="reasoning-block"><summary>Etapas da análise</summary><p>{message.reasoning}</p></details>
                  )}
                  <div className="markdown-body">
                    {message.pending && !message.content ? <div className="typing-indicator" aria-label="Gerando resposta"><span /><span /><span /></div> : message.role === 'assistant' ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown> : <p>{message.content}</p>}
                    {message.pending && message.content && <span className="stream-caret" />}
                  </div>
                  {message.role === 'assistant' && message.content && !message.pending && (
                    <div className="message-footer">
                      {!message.error && (
                        <div className="message-tools">
                          <button onClick={() => props.onCopy(message)} aria-label="Copiar resposta" title="Copiar resposta">{props.copiedId === message.id ? <Check size={15} /> : <Clipboard size={15} />}</button>
                          <button onClick={() => props.onRegenerate(message.id)} aria-label="Gerar novamente" title="Gerar novamente"><RotateCcw size={15} /></button>
                          <button className={message.feedback === 'positive' ? 'selected' : ''} onClick={() => props.onFeedback(message.id, message.feedback === 'positive' ? null : 'positive')} aria-label="Resposta útil" title="Resposta útil"><ThumbsUp size={15} /></button>
                          <button className={message.feedback === 'negative' ? 'selected' : ''} onClick={() => props.onFeedback(message.id, message.feedback === 'negative' ? null : 'negative')} aria-label="Resposta não útil" title="Resposta não útil"><ThumbsDown size={15} /></button>
                        </div>
                      )}
                      {(message.usage?.total_tokens || message.durationMs) && <span className="message-meta">{message.usage?.total_tokens ? `${message.usage.total_tokens.toLocaleString('pt-BR')} tokens` : ''}{message.usage?.total_tokens && message.durationMs ? ' · ' : ''}{message.durationMs ? `${(message.durationMs / 1000).toFixed(1)} s` : ''}</span>}
                    </div>
                  )}
                </div>
              </article>
            ))}
            <div ref={endRef} />
          </div>
        )}
      </section>

      <footer className="composer-area">
        {props.usage?.total_tokens && <div className="latest-usage">Última resposta: {props.usage.total_tokens.toLocaleString('pt-BR')} tokens</div>}
        <div className="composer-v2">
          <textarea
            ref={textareaRef}
            value={props.input}
            onChange={(event) => { props.onInput(event.target.value); resize() }}
            onKeyDown={(event) => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); submit() } }}
            rows={1}
            placeholder={ready ? 'Pergunte à cMob AI' : 'Aguardando conexão com a IA'}
            disabled={!ready || props.isStreaming}
            aria-label="Mensagem para a cMob AI"
          />
          {props.isStreaming ? <button className="composer-submit stop" onClick={props.onStop} aria-label="Interromper resposta"><Square size={14} fill="currentColor" /></button> : <button className="composer-submit" onClick={submit} disabled={!props.input.trim() || !ready} aria-label="Enviar mensagem"><Send size={17} /></button>}
        </div>
        <p>A cMob AI da SEMOB pode cometer erros. Valide decisões críticas com a fonte dos dados.</p>
      </footer>
    </main>
  )
}
