type Props = {
  name: string
  src?: string | null
  size?: 'small' | 'medium' | 'large'
}

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean)
  return `${parts[0]?.[0] ?? 'U'}${parts.length > 1 ? parts.at(-1)?.[0] ?? '' : ''}`.toUpperCase()
}

export default function UserAvatar({ name, src, size = 'medium' }: Props) {
  return (
    <span className={`user-avatar-v2 ${size}`} aria-hidden="true">
      {src ? <img src={src} alt="" /> : initials(name)}
    </span>
  )
}

