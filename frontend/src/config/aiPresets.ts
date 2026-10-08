import type { PresetId, UserSettings } from '../types'

export type Preset = {
  id: PresetId
  label: string
  description: string
  values: Pick<UserSettings, 'temperature' | 'maxTokens' | 'responseMode' | 'analysisDepth'>
}

export const AI_PRESETS: Preset[] = [
  {
    id: 'precise',
    label: 'Preciso',
    description: 'Linguagem objetiva para consultas numéricas.',
    values: { temperature: 0.1, maxTokens: 800, responseMode: 'fast', analysisDepth: 'quick' },
  },
  {
    id: 'balanced',
    label: 'Balanceado',
    description: 'Equilíbrio entre objetividade e contexto.',
    values: { temperature: 0.25, maxTokens: 1200, responseMode: 'balanced', analysisDepth: 'normal' },
  },
  {
    id: 'explanatory',
    label: 'Explicativo',
    description: 'Respostas mais desenvolvidas e contextualizadas.',
    values: { temperature: 0.35, maxTokens: 2400, responseMode: 'balanced', analysisDepth: 'normal' },
  },
  {
    id: 'deep-analysis',
    label: 'Análise profunda',
    description: 'Mais espaço de resposta para interpretações complexas.',
    values: { temperature: 0.2, maxTokens: 4096, responseMode: 'analysis', analysisDepth: 'deep' },
  },
]

export const DEFAULT_SETTINGS: UserSettings = {
  preset: 'balanced',
  temperature: 0.25,
  maxTokens: 1200,
  thinking: false,
  streaming: true,
  responseMode: 'balanced',
  analysisDepth: 'normal',
  theme: 'dark',
  density: 'comfortable',
  chatFontSize: 'normal',
  language: 'pt-BR',
  dateFormat: 'DD/MM/YYYY',
  showTimestamps: false,
  defaultAssistant: 'last',
}

export const MAX_OUTPUT_OPTIONS = [
  { value: 512, label: 'Curta', description: 'Até 512 tokens' },
  { value: 1200, label: 'Média', description: 'Até 1.200 tokens' },
  { value: 2400, label: 'Longa', description: 'Até 2.400 tokens' },
  { value: 4096, label: 'Muito longa', description: 'Até 4.096 tokens' },
]

