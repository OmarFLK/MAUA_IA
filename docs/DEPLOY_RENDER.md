# Deploy de teste: Neon + Render + Vercel

Esta é a arquitetura recomendada para o primeiro deploy:

```text
Navegador -> Vercel (React/Vite) -> Render (FastAPI/Docker) -> Neon (PostgreSQL)
                                         |
                                         -> API Barô
```

O navegador nunca recebe a chave da Barô, a senha do PostgreSQL ou o segredo JWT. O frontend recebe somente a URL pública do backend.

## Antes de começar

1. Envie o projeto para um repositório privado no GitHub.
2. Confirme que `.env` não está no commit.
3. Troque a chave da Barô se ela já foi enviada em conversa, captura de tela ou commit.
4. Não publique os bancos locais, relatórios SEMOB nem arquivos em `data/`.

Arquivos necessários no commit:

- `Dockerfile`
- `render.yaml`
- `alembic.ini` e `alembic/`
- `requirements-api.txt`
- `vercel.json`
- `frontend/`

## Mapa de variáveis e segredos

| Variável | Onde configurar | É segredo? | Valor |
|---|---|---:|---|
| `DATABASE_URL` | Render | Sim | Connection string **pooled** copiada do Neon |
| `BARO_API_KEY` | Render | Sim | Nova chave pessoal da API Barô |
| `JWT_SECRET` | Render | Sim | Gerado automaticamente pelo Blueprint |
| `ALLOWED_ORIGINS` | Render | Não | URL exata da Vercel, sem `/` no final |
| `BARO_BASE_URL` | Render/Blueprint | Não | `https://ia.maua.br/api/v1` |
| `BARO_MODEL` | Render/Blueprint | Não | `google/gemma-3-27b` |
| `VITE_API_BASE_URL` | Vercel | Não, fica público no bundle | URL `.onrender.com` do backend, sem `/` no final |

Nunca configure `DATABASE_URL`, `BARO_API_KEY` ou `JWT_SECRET` na Vercel. Toda variável iniciada por `VITE_` pode ser incorporada ao JavaScript entregue ao navegador.

## 1. Criar o PostgreSQL no Neon

1. Acesse o Neon e escolha **New Project**.
2. Use um nome como `cmob-ai` e crie o projeto na região geograficamente mais próxima do serviço do Render.
3. No painel do projeto, abra **Connect** ou **Connection Details**.
4. Selecione a branch `main`, o banco `neondb` e o papel proprietário criado pelo Neon.
5. Ative **Pooled connection**. O hostname copiado normalmente contém `-pooler`.
6. Copie a connection string completa. Ela se parece com:

```text
postgresql://USUARIO:SENHA@ep-EXEMPLO-pooler.REGIAO.aws.neon.tech/neondb?sslmode=require&channel_binding=require
```

Não altere manualmente a URL. O backend converte o esquema para `asyncpg`, preserva o TLS e remove somente o parâmetro `channel_binding`, que não é aceito pelo driver usado no projeto.

Você não precisa criar as tabelas pelo painel do Neon. O container executa `alembic upgrade head` antes de iniciar a API.

## 2. Criar primeiro o projeto do frontend na Vercel

Esta primeira publicação serve para reservar e descobrir a URL final do frontend.

1. Na Vercel, escolha **Add New > Project** e importe o repositório.
2. Deixe **Root Directory** na raiz do repositório. O `vercel.json` existente entra em `frontend`, executa `npm ci` e `npm run build`, e publica `frontend/dist`.
3. Em **Environment Variables**, ainda não adicione segredos. Você pode deixar `VITE_API_BASE_URL` vazio nesta primeira publicação.
4. Clique em **Deploy**.
5. Copie o domínio de produção, por exemplo `https://cmob-ai.vercel.app`.

Se mudar qualquer variável na Vercel, é necessário fazer um novo deploy para que o valor entre no build do Vite.

## 3. Criar o backend no Render

O caminho recomendado é usar o Blueprint já versionado:

1. No Render, escolha **New > Blueprint**.
2. Conecte o mesmo repositório e selecione a branch de deploy.
3. Confirme o arquivo `render.yaml` da raiz.
4. Quando o Render solicitar valores, preencha:

```text
DATABASE_URL=<connection string pooled completa do Neon>
BARO_API_KEY=<nova chave da Barô>
ALLOWED_ORIGINS=https://cmob-ai.vercel.app
```

5. Confirme a criação do serviço.

O Blueprint já configura:

- runtime Docker;
- plano gratuito para este primeiro teste;
- health check em `/api/ready`;
- `JWT_SECRET` aleatório;
- ambiente de produção;
- contas de demonstração desativadas;
- pool de conexões PostgreSQL;
- endpoint e modelo da Barô.

O container escuta `0.0.0.0` e usa a variável `PORT` fornecida pelo Render. Durante o boot, aplica as migrações Alembic e só depois inicia o Uvicorn.

No plano gratuito/de teste, essa migração no comando de inicialização é suficiente para uma instância. Antes de escalar para múltiplas instâncias, mova `alembic upgrade head` para o **Pre-Deploy Command**, recurso disponível nos planos compatíveis do Render, evitando migrações concorrentes.

## 4. Ligar o frontend ao backend

Depois que o Render fornecer uma URL como `https://cmob-ai-backend.onrender.com`:

1. Abra o projeto na Vercel.
2. Vá a **Settings > Environment Variables**.
3. Crie:

```text
VITE_API_BASE_URL=https://cmob-ai-backend.onrender.com
```

4. Marque **Production**. Marque **Preview** apenas se os previews também puderem usar o mesmo backend.
5. Salve e faça **Redeploy** do último deployment.

Para o primeiro teste, mantenha `ALLOWED_ORIGINS` no Render somente com o domínio de produção da Vercel. Domínios aleatórios de preview não serão aceitos pelo CORS até serem explicitamente configurados.

## 5. Validar o deploy

Teste o backend no PowerShell:

```powershell
Invoke-RestMethod https://cmob-ai-backend.onrender.com/api/health
Invoke-RestMethod https://cmob-ai-backend.onrender.com/api/ready
```

O segundo endpoint deve retornar `status: ready` e `database_ready: true`. Depois:

1. abra a URL da Vercel;
2. crie uma conta nova;
3. faça login;
4. envie uma mensagem ao assistente geral;
5. atualize a página e confirme que a conversa foi preservada.

No Neon, abra **Tables** ou o editor SQL e confirme a criação de `users`, `conversations`, `conversation_messages`, `conversation_states` e `user_preferences`.

## Diagnóstico rápido

| Sintoma | Onde olhar | Causa provável |
|---|---|---|
| Render não inicia | Render > serviço > **Logs** | `DATABASE_URL` incorreta, segredo ausente ou migração falhou |
| `/api/ready` retorna 503 | Logs do Render e Neon | banco indisponível ou schema não aplicado |
| Navegador mostra erro de CORS | `ALLOWED_ORIGINS` no Render | URL da Vercel diferente, com barra final ou domínio de preview |
| Frontend chama a própria Vercel | `VITE_API_BASE_URL` na Vercel | variável ausente ou deploy não refeito |
| Resposta da IA retorna erro | `BARO_API_KEY` no Render | chave inválida/expirada ou endpoint indisponível |
| Primeira requisição demora | Render/Neon free tiers | serviço ou compute estava suspenso e está acordando |

## Limite deste deploy

Autenticação, contas, perfil, conversas, mensagens, preferências e estado de sessão ficam no Neon. O assistente geral funciona com Render + Neon + Barô.

As análises CMob também exigem os artefatos autorizados `semob.duckdb` e `rag.sqlite`. Eles estão fora do Git de propósito e não são incluídos no container atual. Para publicar essa parte, será necessário montá-los em armazenamento persistente autorizado e configurar `SEMOB_DATABASE_PATH` e `SEMOB_RAG_PATH`.

## Documentação oficial consultada

- [Render: Web Services](https://render.com/docs/web-services)
- [Render: Docker](https://render.com/docs/docker)
- [Render: Blueprints](https://render.com/docs/infrastructure-as-code)
- [Render: Blueprint YAML Reference](https://render.com/docs/blueprint-spec)
- [Render: Health Checks](https://render.com/docs/health-checks)
- [Neon: Database branching workflow](https://neon.com/docs/get-started-with-neon/workflow-primer)
- [Neon: Manage computes and pooled connections](https://neon.com/docs/manage/endpoints/)
- [Vercel: Environment Variables](https://vercel.com/docs/environment-variables)
- [Vercel: Vite](https://vercel.com/docs/frameworks/frontend/vite)
- [Vercel: Monorepos](https://vercel.com/docs/monorepos)
