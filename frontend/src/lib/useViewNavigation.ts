import { useEffect, useRef, useState } from 'react'
import { pathFor, viewFromPath } from './routing'
import type { AppView } from '../types'

type NavigationEntry = { session: string; depth: number }

export function useViewNavigation() {
  const [view, setView] = useState<AppView>(() => viewFromPath(window.location.pathname))
  const session = useRef(crypto.randomUUID())

  useEffect(() => {
    window.history.replaceState({ ...window.history.state, cmobNavigation: { session: session.current, depth: 0 } }, '')
    const popstate = () => setView(viewFromPath(window.location.pathname))
    window.addEventListener('popstate', popstate)
    return () => window.removeEventListener('popstate', popstate)
  }, [])

  function navigate(nextView: AppView, replace = false) {
    const path = pathFor(nextView)
    setView(nextView)
    if (window.location.pathname === path) return
    const entry = window.history.state?.cmobNavigation as NavigationEntry | undefined
    const depth = entry?.session === session.current ? entry.depth : 0
    const state = { ...window.history.state, cmobNavigation: { session: session.current, depth: replace ? depth : depth + 1 } }
    if (replace) window.history.replaceState(state, '', path)
    else window.history.pushState(state, '', path)
  }

  function goBack(): boolean {
    const entry = window.history.state?.cmobNavigation as NavigationEntry | undefined
    // Only traverse entries made by this app session, never an external page.
    if (entry?.session !== session.current || entry.depth < 1) return false
    window.history.back()
    return true
  }

  return { view, navigate, goBack }
}
