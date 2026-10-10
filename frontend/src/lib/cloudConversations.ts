import { apiUrl } from '../api'
import type { Conversation, ChatMessage } from '../types'

type RemoteConversation = {
  id: string
  title: string
  assistant_mode: Conversation['assistantMode']
  updated_at: string
  messages: {
    id: number; role: ChatMessage['role']; content: string; created_at: string
    reasoning: string | null; feedback: ChatMessage['feedback']; usage: ChatMessage['usage']
    duration_ms: number | null; ttft_ms: number | null
  }[]
}

export async function cloudRequest(token: string, path: string, method = 'GET', body?: unknown, signal?: AbortSignal) {
  const response = await fetch(apiUrl(path), {
    method, headers: { Authorization: `Bearer ${token}`, ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    body: body === undefined ? undefined : JSON.stringify(body), signal,
  })
  if (!response.ok) {
    const payload = await response.json().catch(() => null) as { detail?: string } | null
    throw new Error(payload?.detail ?? `Falha ao sincronizar conversas (HTTP ${response.status}).`)
  }
  return response
}

function fromRemote(item: RemoteConversation): Conversation {
  return {
    id: item.id, cloud: true, title: item.title, assistantMode: item.assistant_mode, updatedAt: Date.parse(item.updated_at),
    messages: item.messages.map((message) => ({
      id: `server-${message.id}`, role: message.role, content: message.content, createdAt: Date.parse(message.created_at),
      reasoning: message.reasoning ?? undefined, feedback: message.feedback, usage: message.usage ?? undefined,
      durationMs: message.duration_ms ?? undefined, ttftMs: message.ttft_ms ?? undefined,
    })),
  }
}

export async function fetchCloudConversation(token: string, id: string, signal?: AbortSignal): Promise<Conversation> {
  const response = await cloudRequest(token, `/api/conversations/${encodeURIComponent(id)}`, 'GET', undefined, signal)
  return fromRemote(await response.json() as RemoteConversation)
}

export async function fetchCloudHistory(token: string, signal: AbortSignal): Promise<Conversation[]> {
  const history: Conversation[] = []
  const limit = 25
  for (let offset = 0; ; offset += limit) {
    const response = await cloudRequest(token, `/api/conversation-history?limit=${limit}&offset=${offset}`, 'GET', undefined, signal)
    const page = await response.json() as RemoteConversation[]
    history.push(...page.map(fromRemote))
    if (page.length < limit) return history
  }
}

export async function migrateLocalHistory(token: string, userId: string, local: Conversation[], signal: AbortSignal) {
  const key = `cmob-ai-cloud-migrated-v1:${userId}`
  try { if (localStorage.getItem(key)) return } catch { /* Cloud history does not require browser storage. */ }
  for (const conversation of local) {
    const messages = conversation.messages.filter((message) => !message.pending && !message.error && message.content.trim())
    if (!messages.length) continue
    await cloudRequest(token, '/api/conversations/import', 'POST', {
      id: conversation.id, title: conversation.title.slice(0, 80), assistant_mode: conversation.assistantMode,
      messages: messages.map(({ role, content, reasoning, createdAt }) => ({ role, content, reasoning, created_at: new Date(createdAt).toISOString() })),
    }, signal)
  }
  try { localStorage.setItem(key, 'true') } catch { /* Import is idempotent if this marker cannot be saved. */ }
}

export function mergeCloudHistory(remote: Conversation[], local: Conversation[]): Conversation[] {
  const ids = new Set(remote.map((item) => item.id))
  const drafts = local.filter((item) => !item.cloud && !item.messages.length && !ids.has(item.id))
  const hydrated = remote.map((conversation) => {
    const cached = local.find((item) => item.id === conversation.id)
    return { ...conversation, messages: conversation.messages.map((message, index) => {
      const previous = cached?.messages[index]
      if (!previous || previous.content !== message.content || previous.role !== message.role) return message
      return { ...message, reasoning: message.reasoning ?? previous.reasoning, feedback: message.feedback ?? previous.feedback,
        usage: message.usage ?? previous.usage, durationMs: message.durationMs ?? previous.durationMs, ttftMs: message.ttftMs ?? previous.ttftMs }
    }) }
  })
  return [...hydrated, ...drafts]
}
