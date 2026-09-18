# Mauá AI Chat

Chat acadêmico com React + TypeScript, FastAPI e PostgreSQL para consumir a API OpenAI-compatible hospedada na Mauá.

## O que está incluído

- Login, cadastro e sessão JWT.
- Senhas protegidas com hash Argon2; senhas nunca são armazenadas em texto puro.
- Usuários persistidos no PostgreSQL.
- Chat protegido: somente usuários autenticados acessam a IA.
- Streaming, Markdown, ajustes de temperatura e raciocínio.
- Conversas locais separadas por usuário no navegador.
- Três usuários de teste criados automaticamente em desenvolvimento.

## Executar localmente

### 1. Configuração

Copie o arquivo de exemplo se ainda não existir um `.env`:

```powershell
Copy-Item .env.example .env
```

Quando a Mauá fornecer o endereço, substitua `MAUA_AI_BASE_URL` pela URL real terminada em `/v1`.

### 2. PostgreSQL

Com Docker Desktop instalado e aberto:

```powershell
docker compose up -d postgres
```

O Compose cria o banco `maua_ai` e mantém seus dados em um volume. Também é possível usar PostgreSQL gratuito do Supabase ou Neon, substituindo `DATABASE_URL` no `.env`.

### 3. Backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

As tabelas e os usuários de teste são criados ao iniciar o backend.

### 4. Frontend

Em outro terminal:

```powershell
cd frontend
npm install
npm run dev
```

Abra [http://localhost:5173](http://localhost:5173).

## Contas de teste

| Nome | E-mail | Senha |
|---|---|---|
| Ana Silva | `ana@teste.maua.ai` | `Maua@2026` |
| Bruno Santos | `bruno@teste.maua.ai` | `Maua@2026` |
| Carla Oliveira | `carla@teste.maua.ai` | `Maua@2026` |

Elas só são criadas quando `SEED_TEST_USERS=true`. No deploy público, altere para `false` e remova essas contas do banco.

## Validação

```powershell
# Backend
.\.venv\Scripts\python.exe -m pytest backend\test_main.py -q

# Frontend
cd frontend
npm run lint
npm run build
```

## Antes do deploy

- Gere um `JWT_SECRET` longo e aleatório.
- Configure `SEED_TEST_USERS=false`.
- Restrinja `ALLOWED_ORIGINS` ao domínio real do frontend.
- Use uma conexão PostgreSQL com senha forte e TLS.
- Não exponha `MAUA_AI_BASE_URL`, `DATABASE_URL` ou `JWT_SECRET` no frontend.
- Mantenha o backend na VM cujo IPv4 fixo será liberado pela Mauá.

