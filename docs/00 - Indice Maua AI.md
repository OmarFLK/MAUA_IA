---
aliases:
  - Documentação Mauá AI
  - Projeto Mauá AI
tags:
  - projeto
  - inteligencia-artificial
  - maua
  - chatbot
status: em-desenvolvimento
atualizado: 2026-09-25
---

# Mauá AI — documentação do projeto

> [!abstract] Resumo
> Aplicação web de chatbot acadêmico que conecta alunos à IA executada nos servidores da Mauá. O sistema possui frontend em React, backend em FastAPI, autenticação com JWT e usuários armazenados no PostgreSQL.

## Navegação

- [[01 - Deploy e IP fixo|Deploy, IP fixo e liberação com o professor]]
- [[02 - Migracao para outro PC|Migração e instalação no PC novo]]
- [Uso em casa, na Mauá e em redes com IPs diferentes](03%20-%20Uso%20em%20redes%20e%20IPs%20diferentes.md)
- [README técnico](../README.md)
- [Repositório no GitHub](https://github.com/OmarFLK/MAUA_IA)

## Objetivo

Criar uma interface segura e simples para utilizar o modelo de IA disponibilizado pela Mauá em PI, TCC e trabalhos de disciplinas. O navegador nunca acessa diretamente a API institucional: todas as chamadas passam pelo nosso backend autenticado.

## IA utilizada

| Item | Valor atual |
|---|---|
| Modelo principal | `google/gemma-3-27b` |
| Família | Gemma 3 |
| Parâmetros | 27 bilhões |
| Licença | Gemma Terms of Use |
| Contexto do modelo de referência | 128 mil tokens |
| Multimodal | O modelo aceita texto e imagem; a interface atual usa apenas texto |
| Compatibilidade | API no padrão OpenAI |
| Streaming | SSE, convertido pelo backend para NDJSON no navegador |
| Temperatura padrão | `0.25` |
| Timeout | 120 segundos |

> [!important] Identificador do modelo
> O professor informou o identificador `google/gemma-3-27b`. O endpoint `/v1/models` deve ser consultado a partir da rede da Mauá para confirmar a instalação disponível no servidor.

O ajuste `enable_thinking`, específico do modelo Qwen usado anteriormente, não é enviado ao Gemma. A interface oculta essa opção quando o backend informa que ela não é suportada.

## Arquitetura

```mermaid
flowchart LR
    U[Usuário] -->|HTTPS| F[Frontend React<br/>Vercel]
    F -->|JWT + HTTPS| B[Backend FastAPI<br/>VM com IPv4 fixo]
    B -->|Rede autorizada| M[API de IA da Mauá<br/>Gemma 3 27B]
    B -->|TLS| P[(PostgreSQL<br/>Supabase, Neon ou VM)]
    F -->|localStorage| H[(Histórico local<br/>por usuário)]
```

### Como o acesso está liberado atualmente?

O professor liberou as requisições originadas na rede da Mauá. Fora dela, o IP público de saída do backend precisa de autorização específica. Isso vale para casa e para nuvem. A Base URL e o modelo continuam iguais ao trocar de rede; veja o guia de redes acima para diagnóstico e solicitação de acesso.

O frontend e o PostgreSQL podem ficar em outros provedores. Apenas o servidor que chama diretamente a API da Mauá precisa ter o IP liberado.

## Tecnologias

### Frontend

- React + TypeScript
- Vite
- React Markdown + GitHub Flavored Markdown
- Lucide Icons
- Histórico salvo no `localStorage`, separado pelo ID do usuário
- Token de sessão salvo no `sessionStorage`

### Backend

- Python + FastAPI
- HTTPX para comunicação e streaming com a Mauá
- SQLAlchemy assíncrono
- JWT para autenticação
- Argon2 para hash das senhas
- Validação com Pydantic

### Dados e infraestrutura

- PostgreSQL para usuários
- Docker Compose para banco local
- Vercel preparada para o frontend
- Backend planejado para uma VM com IPv4 fixo

## Como uma mensagem percorre o sistema

1. O usuário entra ou cria uma conta.
2. O backend confere o PostgreSQL e entrega um token JWT.
3. O frontend envia a pergunta e o token ao endpoint `/api/chat`.
4. O backend valida o usuário.
5. O backend resolve o contexto analítico, acrescenta as evidências e envia até 30 mensagens recentes ao modelo. Se o cliente envia apenas a pergunta atual, recupera a memória local daquela conversa e usuário.
6. A chamada é enviada para `{MAUA_AI_BASE_URL}/chat/completions`.
7. A Mauá responde em streaming.
8. O backend repassa os fragmentos ao navegador conforme chegam.
9. O navegador renderiza Markdown e salva a conversa localmente.

## O que já está pronto

- [x] Interface responsiva do chat
- [x] Streaming das respostas
- [x] Renderização de Markdown, código e tabelas
- [x] Histórico local com várias conversas
- [x] Configuração de temperatura e limite de resposta
- [x] Tela de login e cadastro
- [x] Usuários no PostgreSQL
- [x] Senhas com Argon2
- [x] Sessão JWT e endpoint `/api/auth/me`
- [x] Chat protegido contra acesso sem autenticação
- [x] Históricos locais separados por usuário
- [x] Três contas demonstrativas
- [x] Docker Compose para PostgreSQL local
- [x] Configuração de build do frontend na Vercel
- [x] Nove testes automatizados do backend
- [x] Lint, TypeScript e build de produção validados
- [x] Código versionado no GitHub

## O que ainda falta

> [!todo] Caminho crítico
> Os itens abaixo precisam ser concluídos nesta ordem para testar a IA real.

- [ ] Criar a VM gratuita ou VPS para o backend
- [ ] Reservar um IPv4 público permanente nessa VM
- [ ] Enviar o IPv4 ao professor
- [x] Receber a Base URL da API da Mauá
- [x] Confirmar acesso para requisições originadas na rede da Mauá
- [ ] Escolher e criar o PostgreSQL de produção
- [ ] Publicar o backend com HTTPS
- [ ] Configurar os segredos de produção no backend
- [ ] Publicar ou atualizar o frontend na Vercel
- [ ] Configurar `VITE_API_BASE_URL` na Vercel
- [ ] Adicionar o domínio da Vercel em `ALLOWED_ORIGINS`
- [ ] Confirmar o modelo usando `/v1/models`
- [ ] Executar um teste completo de login → pergunta → streaming
- [ ] Desativar e remover as contas demonstrativas antes do uso real

## Contas de desenvolvimento

| Nome | E-mail | Senha |
|---|---|---|
| Ana Silva | `ana@teste.maua.ai` | `SEED_TEST_PASSWORD` do `.env` local |
| Bruno Santos | `bruno@teste.maua.ai` | `SEED_TEST_PASSWORD` do `.env` local |
| Carla Oliveira | `carla@teste.maua.ai` | `SEED_TEST_PASSWORD` do `.env` local |

> [!warning] Produção
> Essas contas são apenas para desenvolvimento. Antes do deploy real, usar `SEED_TEST_USERS=false` e excluir os usuários demonstrativos do banco.

## Onde cada dado fica

| Dado | Local | Observação |
|---|---|---|
| Nome e e-mail | PostgreSQL | Persistentes |
| Senha | PostgreSQL | Somente hash Argon2 |
| Token JWT | `sessionStorage` | Some ao fechar a sessão do navegador |
| Conversas | `localStorage` | Separadas por usuário e por navegador |
| Base URL da Mauá | Variável do backend | Nunca vai para o frontend |
| Segredo JWT | Variável do backend | Nunca deve entrar no Git |
| URL pública do backend | Variável da Vercel | Não é um segredo |

O histórico visual fica no navegador. O backend também mantém memória e estado analítico em SQLite local, separados por usuário e conversa. Esses arquivos não entram no Git e não sincronizam automaticamente a interface entre computadores. PostgreSQL não armazena essa memória atualmente.

## Estrutura do repositório

```text
MAUA_IA/
├── backend/
│   ├── auth.py           # cadastro, login, JWT e usuário atual
│   ├── config.py         # variáveis de ambiente
│   ├── database.py       # conexão, sessões e contas de teste
│   ├── main.py           # API, integração com a Mauá e streaming
│   ├── models.py         # tabela de usuários
│   └── test_main.py      # testes automatizados
├── frontend/
│   ├── src/App.tsx       # interface principal do chat
│   ├── src/AuthScreen.tsx# login e cadastro
│   ├── src/api.ts        # endereço público do backend
│   └── src/styles.css    # design responsivo
├── docs/                 # documentação para Obsidian
├── docker-compose.yml    # PostgreSQL local
├── vercel.json           # build do frontend na Vercel
├── .env.example          # modelo das variáveis do backend
└── README.md             # instruções técnicas rápidas
```

## Melhorias futuras

- [ ] Persistir conversas e mensagens no PostgreSQL
- [ ] Recuperação de senha por e-mail
- [ ] Painel administrativo para usuários e consumo
- [ ] Rate limiting por usuário e por IP
- [ ] Refresh token ou sessão por cookie seguro
- [ ] Upload de imagens para usar a capacidade multimodal
- [ ] Métricas de latência, falhas e tamanho das respostas
- [ ] Migrações formais de banco com Alembic
- [ ] Testes ponta a ponta do frontend

## Contatos da Mauá

- Responsável técnico: consulte o professor pelo canal institucional da disciplina.
- Grupo de suporte: solicite o convite ao responsável por canal privado.

---

Próximo passo recomendado: conectar o computador à rede da Mauá e executar o teste completo de login, modelos e streaming.

