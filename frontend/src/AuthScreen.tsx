import { FormEvent, useState } from 'react'
import {
  ArrowRight,
  Check,
  Database,
  Eye,
  EyeOff,
  GraduationCap,
  LoaderCircle,
  LockKeyhole,
  Mail,
  ShieldCheck,
  Sparkles,
  UserRound,
} from 'lucide-react'
import { apiUrl } from './api'

export type AuthUser = {
  id: string
  name: string
  email: string
}

export type AuthPayload = {
  access_token: string
  token_type: string
  user: AuthUser
}

type Props = {
  onAuthenticated: (payload: AuthPayload) => void
}

const testAccounts = [
  { name: 'Ana', email: 'ana@teste.maua.ai' },
  { name: 'Bruno', email: 'bruno@teste.maua.ai' },
  { name: 'Carla', email: 'carla@teste.maua.ai' },
]

function errorMessage(payload: unknown): string {
  if (!payload || typeof payload !== 'object' || !('detail' in payload)) return 'Não foi possível concluir. Tente novamente.'
  const detail = (payload as { detail: unknown }).detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail[0] && typeof detail[0] === 'object' && 'msg' in detail[0]) {
    return String(detail[0].msg).replace('Value error, ', '')
  }
  return 'Confira os dados informados e tente novamente.'
}

export default function AuthScreen({ onAuthenticated }: Props) {
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const showTestAccounts = import.meta.env.DEV || import.meta.env.VITE_SHOW_TEST_ACCOUNTS === 'true'

  function changeMode(nextMode: 'login' | 'register') {
    setMode(nextMode)
    setError('')
    setPassword('')
    setConfirmPassword('')
  }

  function fillTestAccount(accountEmail: string) {
    setMode('login')
    setEmail(accountEmail)
    setPassword('Maua@2026')
    setError('')
  }

  async function submit(event: FormEvent) {
    event.preventDefault()
    setError('')
    if (mode === 'register' && password !== confirmPassword) {
      setError('As senhas não coincidem.')
      return
    }

    setLoading(true)
    try {
      const response = await fetch(apiUrl(`/api/auth/${mode}`), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(mode === 'login' ? { email, password } : { name, email, password }),
      })
      const payload = (await response.json().catch(() => null)) as AuthPayload | null
      if (!response.ok || !payload?.access_token) throw new Error(errorMessage(payload))
      onAuthenticated(payload)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Não foi possível conectar ao servidor.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="auth-page">
      <section className="auth-story">
        <div className="auth-brand">
          <div className="brand-mark"><Sparkles size={20} /></div>
          <div className="brand-name">Mauá <span>AI</span></div>
        </div>

        <div className="auth-story-content">
          <div className="auth-kicker"><span /> AMBIENTE ACADÊMICO SEGURO</div>
          <h1>Ideias melhores<br />começam com uma<br /><em>boa conversa.</em></h1>
          <p>Seu assistente acadêmico conectado à infraestrutura de IA da Mauá.</p>
          <div className="auth-benefits">
            <div><ShieldCheck size={19} /><span><strong>Acesso protegido</strong>Somente usuários cadastrados</span></div>
            <div><Database size={19} /><span><strong>Dados controlados</strong>Credenciais protegidas no PostgreSQL</span></div>
            <div><GraduationCap size={19} /><span><strong>Feito para projetos</strong>PI, TCC e disciplinas</span></div>
          </div>
        </div>
        <p className="auth-institution">Instituto Mauá de Tecnologia</p>
      </section>

      <section className="auth-panel">
        <div className="auth-card">
          <div className="auth-mobile-brand">
            <div className="brand-mark"><Sparkles size={18} /></div>
            <div className="brand-name">Mauá <span>AI</span></div>
          </div>
          <div className="auth-heading">
            <p>{mode === 'login' ? 'BEM-VINDO DE VOLTA' : 'COMECE AGORA'}</p>
            <h2>{mode === 'login' ? 'Entre na sua conta' : 'Crie sua conta'}</h2>
            <span>{mode === 'login' ? 'Continue de onde você parou.' : 'Use seus dados para acessar o assistente.'}</span>
          </div>

          <div className="auth-tabs" role="tablist">
            <button className={mode === 'login' ? 'active' : ''} onClick={() => changeMode('login')} type="button">Entrar</button>
            <button className={mode === 'register' ? 'active' : ''} onClick={() => changeMode('register')} type="button">Criar conta</button>
          </div>

          <form className="auth-form" onSubmit={submit}>
            {mode === 'register' && (
              <label>
                <span>Nome completo</span>
                <div className="auth-input"><UserRound size={17} /><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Seu nome" minLength={2} maxLength={80} autoComplete="name" required /></div>
              </label>
            )}
            <label>
              <span>E-mail</span>
              <div className="auth-input"><Mail size={17} /><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="voce@email.com" autoComplete="email" required /></div>
            </label>
            <label>
              <span>Senha</span>
              <div className="auth-input">
                <LockKeyhole size={17} />
                <input type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} placeholder={mode === 'register' ? 'Mínimo de 8 caracteres' : 'Sua senha'} minLength={mode === 'register' ? 8 : 1} maxLength={128} autoComplete={mode === 'login' ? 'current-password' : 'new-password'} required />
                <button type="button" onClick={() => setShowPassword((visible) => !visible)} aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}>{showPassword ? <EyeOff size={17} /> : <Eye size={17} />}</button>
              </div>
            </label>
            {mode === 'register' && (
              <label>
                <span>Confirmar senha</span>
                <div className="auth-input"><Check size={17} /><input type={showPassword ? 'text' : 'password'} value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} placeholder="Digite novamente" minLength={8} maxLength={128} autoComplete="new-password" required /></div>
              </label>
            )}
            {error && <div className="auth-error" role="alert">{error}</div>}
            <button className="auth-submit" disabled={loading}>
              {loading ? <LoaderCircle className="spin" size={18} /> : <>{mode === 'login' ? 'Entrar no chat' : 'Criar minha conta'} <ArrowRight size={18} /></>}
            </button>
          </form>

          {showTestAccounts && mode === 'login' && (
            <div className="test-accounts">
              <div className="test-divider"><span /> Contas de teste <span /></div>
              <div className="test-list">
                {testAccounts.map((account) => (
                  <button key={account.email} type="button" onClick={() => fillTestAccount(account.email)}>
                    <span>{account.name[0]}</span><div><strong>{account.name}</strong><small>{account.email}</small></div>
                  </button>
                ))}
              </div>
              <p>Senha para todas: <code>Maua@2026</code></p>
            </div>
          )}
        </div>
      </section>
    </main>
  )
}
