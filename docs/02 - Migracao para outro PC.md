---
tags:
  - projeto
  - setup
  - migracao
  - windows
status: pronto
atualizado: 2026-10-02
---

# Migração para outro PC

← [[00 - Indice Maua AI|Voltar para a documentação principal]]

> [!success] O que precisa ser transferido
> O código e esta documentação já estão no GitHub. Não copie `.venv`, `node_modules` ou `dist`; essas pastas são recriadas no PC novo. O arquivo `.env` não está no Git por segurança e deve ser recriado ou transferido separadamente.

## Pré-requisitos no PC novo

- Git
- Node.js 22 ou versão LTS compatível
- Python 3.11 ou superior
- Docker Desktop, caso use PostgreSQL local
- Obsidian, se quiser abrir estas notas como vault
- Um editor como VS Code ou Cursor

## 1. Clonar o projeto

```powershell
cd C:\caminho\onde\guardar
git clone https://github.com/OmarFLK/MAUA_IA.git
cd MAUA_IA
```

Conferir:

```powershell
git status
git log -1 --oneline
```

## 2. Recriar o `.env`

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

> [!warning] Segredos
> Nunca envie o `.env` pelo GitHub, Discord ou mensagem pública. Para migrar os valores reais, use um gerenciador de senhas ou transferência privada. O `.env.example` contém apenas os nomes das configurações, sem endpoint institucional ou segredos privados.

No desenvolvimento local, os valores principais são:

```env
DATABASE_URL=sqlite+aiosqlite:///./maua_ai.db
SEED_TEST_USERS=false
```

SQLite é o padrão local sem Docker; o driver está em `requirements-dev.txt`. Nesse caso, pule a etapa 3. Preencha também os valores obrigatórios abaixo antes de iniciar:

| Variável local | Como configurar |
|---|---|
| `BARO_BASE_URL` | `https://ia.maua.br/api/v1` |
| `BARO_API_KEY` | Sua chave pessoal da Barô; use apenas no `.env` |
| `BARO_MODEL` | `google/gemma-3-27b` |
| `JWT_SECRET` | Gere um segredo aleatório com pelo menos 32 caracteres; sem ele o backend não inicia |
| `SEED_TEST_PASSWORD` | Necessária apenas se `SEED_TEST_USERS=true`, mínimo 8 caracteres |
| `POSTGRES_PASSWORD` | Necessária apenas para PostgreSQL no Docker |
| `DATABASE_URL` | SQLite conforme acima, ou URL PostgreSQL com credenciais locais |

Para gerar um segredo na sua máquina:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

Use valores diferentes para JWT, contas e banco. Guarde-os no `.env`, nunca na documentação, no frontend ou no Git. A chave da Mauá não pode ser substituída por um valor aleatório. Para criar sua própria conta na interface, mantenha `SEED_TEST_USERS=false`.

## 3. Subir o PostgreSQL

Somente se escolher PostgreSQL: preencha `POSTGRES_PASSWORD` no `.env` e configure `DATABASE_URL` no formato `postgresql+asyncpg://USUARIO:SENHA@localhost:5432/NOME_DO_BANCO`, substituindo os campos pelos valores locais. O Compose usa usuário `maua` e banco `maua_ai`; a senha é lida de `POSTGRES_PASSWORD`. Caracteres especiais na senha devem ser codificados para uso na URL. A variável do Compose não altera a senha de um volume PostgreSQL já inicializado.

Abrir o Docker Desktop e executar:

```powershell
docker compose up -d postgres
docker compose ps
```

Para acompanhar o banco:

```powershell
docker compose logs -f postgres
```

Os dados ficam em um volume Docker chamado `maua_postgres_data` e não somem quando o container é apenas parado.

## 4. Preparar o backend

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Antes de iniciar, transfira os relatórios HTML autorizados para `data/raw`, preservando a estrutura das pastas. Esses dados não estão no GitHub. Não copie bancos com o backend em execução; para migrar também memória e usuários, pare os serviços e faça backup privado dos arquivos e configurações.

Reconstrua a base analítica e o índice textual:

```powershell
.\.venv\Scripts\python.exe -m scripts.ingest_semob
.\.venv\Scripts\python.exe -m scripts.index_documents
```

Iniciar o backend e manter o terminal aberto:

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000
```

O backend deve responder em:

- `http://127.0.0.1:8000/api/health`
- `http://127.0.0.1:8000/docs`

## 5. Preparar o frontend

Em outro terminal:

```powershell
cd frontend
npm.cmd ci
npm.cmd run dev
```

Abrir `http://localhost:5173`.

No desenvolvimento local, `VITE_API_BASE_URL` pode ficar vazio, pois o Vite encaminha `/api` para `127.0.0.1:8000`.

O atalho `.\start-local.cmd` da instalação original espera Node portátil em `../.tools/node`; essa pasta não está no Git. Os dois terminais descritos aqui funcionam com Python e Node instalados no PC, sem copiar `.tools`. Para interromper a execução manual, use `Ctrl+C` em cada terminal.

Antes de testar o modelo na faculdade ou em casa, siga [uso em redes e IPs diferentes](03%20-%20Uso%20em%20redes%20e%20IPs%20diferentes.md). A configuração do projeto não concede autorização ao IP de saída da rede.

## 6. Testar as contas

| Usuário | Senha |
|---|---|
| `ana@teste.maua.ai` | Valor local de `SEED_TEST_PASSWORD` na criação da conta |
| `bruno@teste.maua.ai` | Valor local de `SEED_TEST_PASSWORD` na criação da conta |
| `carla@teste.maua.ai` | Valor local de `SEED_TEST_PASSWORD` na criação da conta |

Também deve ser possível criar uma nova conta pela aba **Criar conta**.

As contas da tabela só são criadas com `SEED_TEST_USERS=true` e uma senha configurada. Alterar a variável não redefine contas existentes. Senhas de demonstração de versões anteriores já foram públicas; remova/substitua essas contas antes de publicar. Não é necessário apagar o banco para migrar o projeto.

## 7. Rodar as verificações

Na raiz:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

No frontend:

```powershell
cd frontend
npm.cmd run lint
npm.cmd run build
```

Resultado de referência da última validação:

- Python: 64 testes aprovados na validação de 01/10/2026
- Frontend: lint aprovado
- TypeScript: aprovado
- Build Vite: aprovado

## 8. Abrir no Obsidian

Há duas opções:

1. Abrir a pasta `MAUA_IA` diretamente como um novo vault; ou
2. Manter o repositório dentro do seu vault principal.

A nota inicial é:

```text
docs/00 - Indice Maua AI.md
```

## Checklist final da migração

- [ ] Repositório clonado
- [ ] `.env` recriado
- [ ] Banco de usuários configurado: SQLite local ou PostgreSQL saudável
- [ ] Ambiente virtual Python criado
- [ ] Dependências Python instaladas
- [ ] Dependências npm instaladas
- [ ] Relatórios autorizados transferidos e base DuckDB reconstruída
- [ ] Índice RAG reconstruído
- [ ] Acesso à API da Mauá confirmado a partir da rede atual
- [ ] Backend respondendo em `/api/health`
- [ ] Frontend abrindo em `localhost:5173`
- [ ] Login de teste funcionando
- [ ] Cadastro funcionando
- [ ] Testes e build aprovados
- [ ] Documentação aberta no Obsidian

## Comandos do dia a dia

Atualizar o PC com mudanças do GitHub:

```powershell
git pull
```

Enviar uma alteração:

```powershell
git status
git add .
git commit -m "descricao da alteracao"
git push
```

Parar o banco:

```powershell
docker compose stop postgres
```

> [!danger] Cuidado
> Não use `docker compose down -v` se quiser preservar o banco local. O argumento `-v` remove o volume e apaga os dados.

