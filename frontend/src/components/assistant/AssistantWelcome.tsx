import { ArrowRight, Network, Sparkles } from 'lucide-react'
import type { AssistantMode } from '../../types'
import Brand from '../ui/Brand'

type Props = {
  onSelect: (mode: AssistantMode) => void
}

export default function AssistantWelcome({ onSelect }: Props) {
  return (
    <main className="assistant-welcome-page">
      <header><Brand /></header>
      <section className="assistant-welcome-content">
        <p className="section-kicker">DOIS ASSISTENTES · UM ÚNICO GEMMA</p>
        <h1>Como deseja utilizar a plataforma?</h1>
        <p>Escolha o ambiente ideal para o que você quer fazer agora. Você poderá trocar a qualquer momento.</p>
        <div className="assistant-choice-grid">
          <button onClick={() => onSelect('cmob')}>
            <span className="assistant-choice-icon"><Network size={24} /></span>
            <span className="assistant-choice-copy">
              <strong>CMob AI</strong>
              <small>Inteligência especializada em mobilidade</small>
              <p>Consulte dados operacionais, compare períodos e analise passageiros, viagens, linhas e quilometragem.</p>
              <b>Entrar no CMob AI <ArrowRight size={15} /></b>
            </span>
          </button>
          <button onClick={() => onSelect('general')}>
            <span className="assistant-choice-icon general"><Sparkles size={24} /></span>
            <span className="assistant-choice-copy">
              <strong>Gemma Livre</strong>
              <small>Assistente de propósito geral</small>
              <p>Use o Gemma 3 27B para programação, escrita, explicações, estudos e conversas gerais.</p>
              <b>Usar Gemma Livre <ArrowRight size={15} /></b>
            </span>
          </button>
        </div>
        <span className="assistant-welcome-model">Ambos utilizam Gemma 3 27B no endpoint institucional.</span>
      </section>
    </main>
  )
}
