import type { ChangeEvent } from 'react'
import { BrainCircuit, MessageSquareText, Palette, RotateCcw, Shield, SlidersHorizontal, Upload, UserRound } from 'lucide-react'
import type { AuthUser } from '../../AuthScreen'
import { AI_PRESETS, DEFAULT_SETTINGS, MAX_OUTPUT_OPTIONS } from '../../config/aiPresets'
import type { AppView, Health, LocalProfile, UserSettings } from '../../types'
import InfoTip from '../ui/InfoTip'
import Toggle from '../ui/Toggle'
import UserAvatar from '../ui/UserAvatar'
import WorkspaceHeader, { type WorkspaceNavigationProps } from '../ui/WorkspaceHeader'

type Props = WorkspaceNavigationProps & {
  view: AppView
  user: AuthUser
  profile: LocalProfile
  settings: UserSettings
  health: Health | null
  onNavigate: (view: AppView) => void
  onProfile: (profile: LocalProfile) => void
  onSettings: (settings: UserSettings) => void
}

const tabs = [
  { id: 'settings-profile' as const, label: 'Perfil', icon: UserRound },
  { id: 'settings-appearance' as const, label: 'Aparência', icon: Palette },
  { id: 'settings-chat' as const, label: 'Chat', icon: MessageSquareText },
  { id: 'settings-ai' as const, label: 'Inteligência artificial', icon: SlidersHorizontal },
  { id: 'settings-memory' as const, label: 'Memória', icon: BrainCircuit },
  { id: 'settings-privacy' as const, label: 'Privacidade', icon: Shield },
]

function SettingRow({ title, description, children }: { title: string; description: string; children: React.ReactNode }) {
  return <div className="setting-row"><div><strong>{title}</strong><p>{description}</p></div><div className="setting-control">{children}</div></div>
}

export default function SettingsPage(props: Props) {
  function patchSettings(patch: Partial<UserSettings>) {
    props.onSettings({ ...props.settings, ...patch })
  }

  function uploadAvatar(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0]
    if (!file) return
    if (!file.type.startsWith('image/') || file.size > 1_500_000) return
    const reader = new FileReader()
    reader.onload = () => props.onProfile({ ...props.profile, avatarDataUrl: String(reader.result) })
    reader.readAsDataURL(file)
  }

  const title = tabs.find((tab) => tab.id === props.view)?.label ?? 'Configurações'
  return (
    <main className="workspace page-workspace">
      <WorkspaceHeader title="Configurações" subtitle="Preferências da sua experiência" onBack={props.onBack} onOpenMenu={props.onOpenMenu} />
      <div className="settings-layout">
        <nav className="settings-tabs" aria-label="Categorias de configuração">
          {tabs.map(({ id, label, icon: Icon }) => <button key={id} className={props.view === id ? 'active' : ''} onClick={() => props.onNavigate(id)}><Icon size={17} />{label}</button>)}
        </nav>
        <section className="settings-content">
          <div className="page-heading"><div><p className="section-kicker">PREFERÊNCIAS</p><h1>{title}</h1></div>{props.view !== 'settings-profile' && <button className="secondary-button" onClick={() => props.onSettings({ ...DEFAULT_SETTINGS })}><RotateCcw size={15} /> Restaurar padrões</button>}</div>

          {props.view === 'settings-profile' && <>
            <div className="profile-editor">
              <UserAvatar name={props.profile.displayName} src={props.profile.avatarDataUrl} size="large" />
              <div><strong>Foto de perfil</strong><p>PNG ou JPG de até 1,5 MB. A imagem fica somente neste navegador.</p><label className="secondary-button file-button"><Upload size={15} /> Escolher imagem<input type="file" accept="image/png,image/jpeg,image/webp" onChange={uploadAvatar} /></label>{props.profile.avatarDataUrl && <button className="text-button danger" onClick={() => props.onProfile({ ...props.profile, avatarDataUrl: null })}>Remover</button>}</div>
            </div>
            <div className="form-grid">
              <label><span>Nome exibido</span><input value={props.profile.displayName} onChange={(event) => props.onProfile({ ...props.profile, displayName: event.target.value })} /></label>
              <label><span>E-mail</span><input value={props.user.email} readOnly /></label>
              <label><span>Função</span><input value={props.user.role ?? 'Não disponível'} readOnly /></label>
              <label><span>Conta criada em</span><input value={props.user.created_at ? new Date(props.user.created_at).toLocaleDateString('pt-BR') : 'Não disponível'} readOnly /></label>
            </div>
            <p className="local-note">Nome e imagem personalizados são salvos localmente. E-mail e acesso vêm da conta autenticada.</p>
          </>}

          {props.view === 'settings-appearance' && <div className="settings-section">
            <SettingRow title="Tema" description="Escolha a aparência da interface."><div className="segmented-control">{(['system', 'dark', 'light'] as const).map((theme) => <button key={theme} className={props.settings.theme === theme ? 'active' : ''} onClick={() => patchSettings({ theme })}>{theme === 'system' ? 'Sistema' : theme === 'dark' ? 'Escuro' : 'Claro'}</button>)}</div></SettingRow>
            <SettingRow title="Densidade" description="Ajuste o espaço entre os elementos."><div className="segmented-control"><button className={props.settings.density === 'comfortable' ? 'active' : ''} onClick={() => patchSettings({ density: 'comfortable' })}>Confortável</button><button className={props.settings.density === 'compact' ? 'active' : ''} onClick={() => patchSettings({ density: 'compact' })}>Compacta</button></div></SettingRow>
            <SettingRow title="Texto do chat" description="Altere apenas o tamanho das mensagens."><select value={props.settings.chatFontSize} onChange={(event) => patchSettings({ chatFontSize: event.target.value as UserSettings['chatFontSize'] })}><option value="small">Pequeno</option><option value="normal">Normal</option><option value="large">Grande</option></select></SettingRow>
          </div>}

          {props.view === 'settings-chat' && <div className="settings-section">
            <SettingRow title="Assistente padrão" description="Escolha qual ambiente abrir depois do login."><select value={props.settings.defaultAssistant} onChange={(event) => patchSettings({ defaultAssistant: event.target.value as UserSettings['defaultAssistant'] })}><option value="last">Último utilizado</option><option value="cmob">CMob AI</option><option value="general">Gemma Livre</option></select></SettingRow>
            <SettingRow title="Resposta em tempo real" description="Exibe a resposta enquanto ela é gerada."><Toggle checked={props.settings.streaming} onChange={(streaming) => patchSettings({ streaming })} label="Resposta em tempo real" /></SettingRow>
            <SettingRow title="Horário das mensagens" description="Mostra o horário ao lado do autor."><Toggle checked={props.settings.showTimestamps} onChange={(showTimestamps) => patchSettings({ showTimestamps })} label="Horário das mensagens" /></SettingRow>
            <SettingRow title="Idioma" description="Idioma usado pela interface."><select value={props.settings.language} disabled><option>Português (Brasil)</option></select></SettingRow>
            <SettingRow title="Formato de data" description="Formato usado no histórico."><select value={props.settings.dateFormat} onChange={(event) => patchSettings({ dateFormat: event.target.value as UserSettings['dateFormat'] })}><option value="DD/MM/YYYY">DD/MM/AAAA</option><option value="YYYY-MM-DD">AAAA-MM-DD</option></select></SettingRow>
          </div>}

          {props.view === 'settings-ai' && <>
            <div className="connection-banner"><span className={props.health?.configured ? 'status-dot online' : 'status-dot'} /><div><strong>{props.health?.configured ? 'Controles conectados ao modelo' : 'Conexão com o modelo indisponível'}</strong><p>Temperatura, limite de saída e raciocínio são enviados ao backend em cada pergunta.</p></div></div>
            <div className="preset-grid">{AI_PRESETS.map((preset) => <button key={preset.id} className={props.settings.preset === preset.id ? 'active' : ''} onClick={() => props.onSettings({ ...props.settings, preset: preset.id, ...preset.values })}><strong>{preset.label}</strong><span>{preset.description}</span></button>)}</div>
            <div className="settings-section">
              <SettingRow title="Temperatura" description="Valores baixos priorizam consistência; valores altos aumentam variação."><div className="range-control"><input type="range" min="0" max="1" step="0.05" value={props.settings.temperature} onChange={(event) => patchSettings({ temperature: Number(event.target.value), preset: 'balanced' })} /><input type="number" min="0" max="1" step="0.05" value={props.settings.temperature} onChange={(event) => patchSettings({ temperature: Number(event.target.value), preset: 'balanced' })} /></div></SettingRow>
              <SettingRow title="Máximo de saída" description="Limite solicitado para a resposta do modelo."><select value={props.settings.maxTokens} onChange={(event) => patchSettings({ maxTokens: Number(event.target.value), preset: 'balanced' })}>{MAX_OUTPUT_OPTIONS.map((option) => <option key={option.value} value={option.value}>{option.label} · {option.description}</option>)}</select></SettingRow>
              <SettingRow title="Raciocínio do modelo" description={props.health?.supports_thinking ? 'Recurso informado como disponível pelo backend.' : 'O backend informa que este recurso não está disponível.'}><Toggle checked={props.settings.thinking} onChange={(thinking) => patchSettings({ thinking })} disabled={!props.health?.supports_thinking} label="Raciocínio do modelo" /></SettingRow>
              <SettingRow title="Modo de resposta" description="Preferência de interface; ainda não há suporte específico no pipeline."><div className="control-with-tip"><select value={props.settings.responseMode} onChange={(event) => patchSettings({ responseMode: event.target.value as UserSettings['responseMode'] })}><option value="fast">Rápido</option><option value="balanced">Equilibrado</option><option value="analysis">Analítico</option></select><InfoTip text="Esta preferência fica salva, mas o backend atual ainda não expõe um parâmetro equivalente." /></div></SettingRow>
              <SettingRow title="Profundidade da análise" description="Preferência local preparada para integração futura."><div className="control-with-tip"><select value={props.settings.analysisDepth} onChange={(event) => patchSettings({ analysisDepth: event.target.value as UserSettings['analysisDepth'] })}><option value="quick">Rápida</option><option value="normal">Normal</option><option value="deep">Profunda</option></select><InfoTip text="Ainda não conectada ao mecanismo de análise." /></div></SettingRow>
            </div>
          </>}

          {props.view === 'settings-memory' && <div className="empty-setting"><BrainCircuit size={24} /><h2>Histórico da conta</h2><span>Retenção de {props.health?.history_retention_days ?? 14} dias</span></div>}
          {props.view === 'settings-privacy' && <div className="settings-section"><SettingRow title="Histórico da conta" description=""><span className="availability success">Salvo no servidor</span></SettingRow><SettingRow title="Prazo de retenção" description=""><span>{props.health?.history_retention_days ?? 14} dias</span></SettingRow><SettingRow title="Preferências deste dispositivo" description=""><span className="availability success">Armazenamento local</span></SettingRow></div>}
        </section>
      </div>
    </main>
  )
}
