import { Waypoints } from 'lucide-react'

type Props = { compact?: boolean }

export default function Brand({ compact = false }: Props) {
  return (
    <div className={`product-brand ${compact ? 'compact' : ''}`} aria-label="cMob AI da SEMOB">
      <span className="product-mark"><Waypoints size={compact ? 17 : 20} strokeWidth={2.1} /></span>
      <span className="product-wordmark"><strong>cMob</strong> AI<small>SEMOB · Inteligência de Mobilidade</small></span>
    </div>
  )
}
