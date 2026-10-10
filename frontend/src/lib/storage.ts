import { DEFAULT_SETTINGS } from '../config/aiPresets'
import type { AssistantMode, Conversation, LocalProfile, UsageRecord, UserSettings } from '../types'

const CONVERSATIONS_KEY = 'cmob-ai-conversations-v2'
const SETTINGS_KEY = 'cmob-ai-settings-v2'
const PROFILE_KEY = 'cmob-ai-profile-v1'
const USAGE_KEY = 'cmob-ai-usage-v1'
const LAST_ASSISTANT_KEY = 'cmob-ai-last-assistant-v1'
const HISTORY_MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000

export function pruneConversationHistory(conversations: Conversation[], now = Date.now()): Conversation[] {
  const cutoff = now - HISTORY_MAX_AGE_MS
  return conversations.flatMap((conversation) => {
    const messages = conversation.messages.filter((message) => Number.isFinite(message.createdAt) && message.createdAt > cutoff)
    if (!messages.length && (conversation.messages.length || conversation.updatedAt <= cutoff)) return []
    return [{ ...conversation, messages }]
  })
}

export function createConversation(assistantMode: AssistantMode = 'cmob'): Conversation {
  return { id: crypto.randomUUID(), title: 'Nova conversa', assistantMode, messages: [], updatedAt: Date.now() }
}

export function loadConversations(userId: string): Conversation[] {
  try {
    const saved = localStorage.getItem(`${CONVERSATIONS_KEY}:${userId}`)
    if (saved) {
      const parsed = JSON.parse(saved) as Conversation[]
      if (Array.isArray(parsed) && parsed.length) {
        const conversations = pruneConversationHistory(parsed.map((conversation) => ({
          ...conversation,
          assistantMode: conversation.assistantMode ?? 'cmob',
          messages: conversation.messages.map((message) => ({ ...message, createdAt: message.createdAt ?? conversation.updatedAt })),
        })))
        if (conversations.length) return conversations
      }
    }
  } catch {
    // A aplicação continua com uma conversa limpa se o armazenamento estiver inválido.
  }
  return [createConversation()]
}

export function saveConversations(userId: string, conversations: Conversation[]) {
  localStorage.setItem(`${CONVERSATIONS_KEY}:${userId}`, JSON.stringify(pruneConversationHistory(conversations)))
}

export function loadSettings(userId: string): UserSettings {
  try {
    const saved = localStorage.getItem(`${SETTINGS_KEY}:${userId}`)
    if (saved) return { ...DEFAULT_SETTINGS, ...(JSON.parse(saved) as Partial<UserSettings>) }
  } catch {
    // Usa os padrões quando a preferência local não puder ser lida.
  }
  return { ...DEFAULT_SETTINGS }
}

export function saveSettings(userId: string, settings: UserSettings) {
  localStorage.setItem(`${SETTINGS_KEY}:${userId}`, JSON.stringify(settings))
}

export function loadProfile(userId: string, fallbackName: string): LocalProfile {
  try {
    const saved = localStorage.getItem(`${PROFILE_KEY}:${userId}`)
    if (saved) return { displayName: fallbackName, avatarDataUrl: null, ...(JSON.parse(saved) as Partial<LocalProfile>) }
  } catch {
    // Mantém os dados da autenticação como fallback.
  }
  return { displayName: fallbackName, avatarDataUrl: null }
}

export function saveProfile(userId: string, profile: LocalProfile) {
  localStorage.setItem(`${PROFILE_KEY}:${userId}`, JSON.stringify(profile))
}

export function loadUsage(userId: string): UsageRecord[] {
  try {
    const saved = localStorage.getItem(`${USAGE_KEY}:${userId}`)
    if (saved) return (JSON.parse(saved) as UsageRecord[]).slice(-500)
  } catch {
    // Métricas locais são opcionais.
  }
  return []
}

export function saveUsage(userId: string, records: UsageRecord[]) {
  localStorage.setItem(`${USAGE_KEY}:${userId}`, JSON.stringify(records.slice(-500)))
}

export function loadLastAssistant(userId: string): AssistantMode | null {
  const value = localStorage.getItem(`${LAST_ASSISTANT_KEY}:${userId}`)
  return value === 'cmob' || value === 'general' ? value : null
}

export function saveLastAssistant(userId: string, mode: AssistantMode) {
  localStorage.setItem(`${LAST_ASSISTANT_KEY}:${userId}`, mode)
}

