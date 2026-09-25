---
tags:
  - projeto
  - setup
  - migracao
  - windows
status: pronto
atualizado: 2026-09-25
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
Copy-Item .env.example .env
notepad .env
```

> [!warning] Segredos
> Nunca envie o `.env` pelo GitHub, Discord ou mensagem pública. Para migrar valores reais, use um gerenciador de senhas ou transferência privada. Enquanto a Base URL da Mauá não existir, mantenha o valor de exemplo.

No desenvolvimento local, os valores principais são:

```env
DATABASE_URL=postgresql+asyncpg://maua:maua_dev_password@localhost:5432/maua_ai
SEED_TEST_USERS=true
```

## 3. Subir o PostgreSQL

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

Iniciar:

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
npm ci
npm run dev
```

Abrir `http://localhost:5173`.

No desenvolvimento local, `VITE_API_BASE_URL` pode ficar vazio, pois o Vite encaminha `/api` para `127.0.0.1:8000`.

## 6. Testar as contas

| Usuário | Senha |
|---|---|
| `ana@teste.maua.ai` | `Maua@2026` |
| `bruno@teste.maua.ai` | `Maua@2026` |
| `carla@teste.maua.ai` | `Maua@2026` |

Também deve ser possível criar uma nova conta pela aba **Criar conta**.

## 7. Rodar as verificações

Na raiz:

```powershell
.\.venv\Scripts\python.exe -m pytest backend\test_main.py -q -p no:cacheprovider
```

No frontend:

```powershell
cd frontend
npm run lint
npm run build
```

Resultado de referência da última validação:

- Backend: 9 testes aprovados
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
- [ ] Docker Desktop funcionando
- [ ] PostgreSQL saudável
- [ ] Ambiente virtual Python criado
- [ ] Dependências Python instaladas
- [ ] Dependências npm instaladas
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

