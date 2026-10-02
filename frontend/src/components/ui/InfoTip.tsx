import { CircleHelp } from 'lucide-react'

export default function InfoTip({ text }: { text: string }) {
  return (
    <span className="info-tip" tabIndex={0} aria-label={text}>
      <CircleHelp size={14} />
      <span role="tooltip">{text}</span>
    </span>
  )
}

