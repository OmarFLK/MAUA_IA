import type { ComponentType } from 'react'

export type Role = 'user' | 'assistant'
export type AssistantMode = 'cmob' | 'general'
export type DefaultAssistant = 'last' | AssistantMode

export type Usage = {
  prompt_tokens?: number
  completion_tokens?: number
  total_tokens?: number
}

export type MessageFeedback = 'positive' | 'negative' | null

export type ChatMessage = {
  id: string
  role: Role
  content: string
  reasoning?: string
  pending?: boolean
  error?: boolean
  createdAt: number
  feedback?: MessageFeedback
  usage?: Usage
  durationMs?: number
  ttftMs?: number
}

export type Conversation = {
  id: string
  title: string
  assistantMode: AssistantMode
  messages: ChatMessage[]
  updatedAt: number
}

export type Health = {
  status: string
  configured: boolean
  database_ready: boolean
  model: string
  supports_thinking: boolean
  analytics_ready: boolean
}

export type AvailableModel = {
  id: string
  object?: string
  owned_by?: string
}

export type UsageRecord = {
  id: string
  timestamp: number
  conversationId: string
  assistantMode?: AssistantMode
  usage?: Usage
  durationMs: number
  ttftMs?: number
  status: 'success' | 'error' | 'cancelled'
}

export type ThemePreference = 'system' | 'dark' | 'light'
export type DensityPreference = 'compact' | 'comfortable'
export type ChatFontSize = 'small' | 'normal' | 'large'
export type ResponseMode = 'fast' | 'balanced' | 'analysis'
export type AnalysisDepth = 'quick' | 'normal' | 'deep'
export type PresetId = 'precise' | 'balanced' | 'explanatory' | 'deep-analysis'

export type UserSettings = {
  preset: PresetId
  temperature: number
  maxTokens: number
  thinking: boolean
  streaming: boolean
  responseMode: ResponseMode
  analysisDepth: AnalysisDepth
  theme: ThemePreference
  density: DensityPreference
  chatFontSize: ChatFontSize
  language: 'pt-BR'
  dateFormat: 'DD/MM/YYYY' | 'YYYY-MM-DD'
  showTimestamps: boolean
  defaultAssistant: DefaultAssistant
}

export type LocalProfile = {
  displayName: string
  avatarDataUrl: string | null
}

export type AppView =
  | 'chat'
  | 'history'
  | 'analyses'
  | 'memory'
  | 'settings-profile'
  | 'settings-appearance'
  | 'settings-chat'
  | 'settings-ai'
  | 'settings-memory'
  | 'settings-privacy'
  | 'admin-overview'
  | 'admin-model'
  | 'admin-ai'

export type NavItem = {
  id: AppView
  label: string
  icon: ComponentType<{ size?: number; strokeWidth?: number }>
}

