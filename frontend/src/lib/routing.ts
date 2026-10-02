import type { AppView } from '../types'

const PATHS: Record<AppView, string> = {
  chat: '/',
  history: '/history',
  analyses: '/analyses',
  memory: '/memory',
  'settings-profile': '/settings/profile',
  'settings-appearance': '/settings/appearance',
  'settings-chat': '/settings/chat',
  'settings-ai': '/settings/ai',
  'settings-memory': '/settings/memory',
  'settings-privacy': '/settings/privacy',
  'admin-overview': '/admin/overview',
  'admin-model': '/admin/model',
  'admin-ai': '/admin/ai',
}

export function pathFor(view: AppView): string {
  return PATHS[view]
}

export function viewFromPath(pathname: string): AppView {
  const match = (Object.entries(PATHS) as [AppView, string][]).find(([, path]) => path === pathname)
  return match?.[0] ?? 'chat'
}

