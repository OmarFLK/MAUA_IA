# Usar o cMob AI com a API Barô

> Atualização: a integração atual usa `BARO_API_KEY` e não depende da antiga allowlist de IP. As orientações de liberação de IP abaixo são históricas e não devem ser aplicadas à API Barô. Para a configuração vigente, siga o README da raiz.

Atualizado em 02/10/2026. [Índice](00%20-%20Indice%20Maua%20AI.md) | [Instalar em outro PC](02%20-%20Migracao%20para%20outro%20PC.md)

## Roteiro rápido na faculdade

Se levar o mesmo notebook já configurado:

1. Conecte-se à rede institucional da Mauá. Uma rede de visitantes pode ter outra saída; confirme o acesso no passo seguinte.
2. Abra o PowerShell na pasta `MAUA_IA`. Mantenha o `.env` atual: não substitua a URL da IA pelo IP da escola.
3. Consulte `/v1/models` seguindo a etapa 3 abaixo, usando a chave do seu `.env` local.
4. Se listar `google/gemma-3-27b`, execute `.\start-local.cmd` e abra http://127.0.0.1:5173.
5. Faça login e teste uma pergunta, depois uma continuação. O teste de geração abaixo ajuda a separar problemas da IA de problemas da aplicação.

Não precisa contratar IP fixo para esse teste dentro da rede autorizada. Se usar um PC diferente da faculdade, faça primeiro a instalação do guia de migração e obtenha os dados por canal autorizado. Sem os relatórios ou a base analítica, o clone sozinho não responde às consultas SEMOB.

## O que precisa ser liberado

O navegador chama nosso backend FastAPI. O backend chama a API do Gemma. A autorização de rede da Mauá considera o **IP público de saída do backend**, não o IP do navegador nem o endereço privado do computador.

```text
Navegador -> backend local ou hospedado -> API da Mauá
                                        verifica a origem do backend
```

Segundo a mensagem do professor, a rede da Mauá está autorizada. Fora dela, peça a liberação da origem externa e confirme o acesso com os testes abaixo. Uma liberação anterior não garante acesso permanente após troca de IP.

| Situação | Origem que precisa de autorização | O que mudar na aplicação |
|---|---|---|
| Backend no notebook dentro da Mauá | Saída da rede da faculdade | Nada, se URL e modelo continuam iguais |
| Backend no notebook em casa | IPv4 público atual da residência | Nada no `.env`; solicitar liberação ao professor |
| Backend usando internet do celular | Saída da operadora móvel | Nova autorização; pode mudar ou ser compartilhada |
| Backend em VM/VPS | IPv4 de saída da VM ou do NAT usado por ela | Segredos e URLs do ambiente de deploy |
| Navegador em casa, backend na nuvem | Saída do backend na nuvem | O IP residencial do visitante não precisa ser liberado na IA |

**A integração Barô atual não usa uma lista de IPs de casa/escola no chatbot.** Use sempre `BARO_BASE_URL=https://ia.maua.br/api/v1` e não coloque endereços residenciais nessa variável.

## Configuração local

Na raiz do projeto, use o `.env` existente. Em uma instalação nova, copie `.env.example` sem sobrescrever segredos já configurados:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
notepad .env
```

Configuração de integração: preencha a URL e a chave somente no `.env`, com os valores recebidos do responsável. A URL deve incluir o caminho da API, normalmente `/v1`:

```env
BARO_BASE_URL=https://ia.maua.br/api/v1
BARO_API_KEY=
BARO_MODEL=google/gemma-3-27b
BARO_SUPPORTS_THINKING=false
BARO_TIMEOUT_SECONDS=120
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Mantenha também as configurações de banco, JWT e dados analíticos da sua instalação. `ALLOWED_ORIGINS` controla as origens do frontend aceitas pelo backend. Preencha `BARO_API_KEY` somente no `.env` local com sua chave pessoal. Nenhuma chave de acesso deve ser publicada, mesmo que usada apenas em testes.

Em um clone novo, `JWT_SECRET` também precisa ser preenchido (mínimo 32 caracteres), e o exemplo usa SQLite local com `requirements-dev.txt`. As contas de teste ficam desativadas por padrão: crie sua conta na interface ou configure `SEED_TEST_PASSWORD` antes de habilitá-las. Veja a tabela completa no guia de migração. Levar o mesmo notebook preserva o `.env` e as contas existentes; um `git pull` não fornece esses segredos a outro PC.

Se o endpoint fornecido usar HTTP, não há proteção TLS no trajeto até a IA. Não envie dados sensíveis sem autorização institucional; solicite HTTPS ou um caminho de rede protegido aprovado para uso real. Ter HTTPS no frontend não protege automaticamente a conexão backend -> IA.

## 1. Descobrir a saída atual

Execute no computador ou servidor onde o backend roda. Funciona no CMD e no PowerShell:

```powershell
curl.exe -4 --fail --silent --show-error --max-time 15 https://api.ipify.org
```

O [ipify](https://www.ipify.org/) informa o IPv4 público visto por esse serviço. É uma consulta externa: o serviço recebe o IP da conexão. `ipconfig` mostra principalmente endereços das interfaces locais, como `192.168.x.x`; esse endereço não serve para a liberação externa.

Um comando não confirma se o contrato da operadora oferece IP fixo. Confirme com a operadora. Reiniciar o modem pode mudar o IP dinâmico, mas não mudar em um teste também não prova que ele é fixo. Em CGNAT, o IPv4 público pode ser compartilhado com outros clientes; avise o responsável antes de pedir a liberação.

VPN, proxy, containers, múltiplos links e rotas por destino podem alterar a saída. O resultado do ipify é um diagnóstico, não uma prova da origem vista pela Mauá. Em caso de divergência, peça ao professor que confira o IP nos logs da requisição à IA.

## 2. Solicitar a autorização

Envie por canal privado, substituindo o campo pelo resultado atual:

> Professor, estou executando o backend do chatbot SEMOB localmente, fora da rede da Mauá. Poderia autorizar o IPv4 público de saída **COLOCAR-IP-AQUI** para acesso à API? A rede é residencial e ainda não confirmei se o IP é fixo. A configuração continua sendo o endpoint informado e o modelo google/gemma-3-27b. Se o IP mudar, aviso para atualizar a autorização e remover o anterior. Obrigado!

Não publique IP residencial, `.env`, tokens ou senhas no repositório. Não é necessário abrir portas no roteador nem desativar o firewall para essas conexões de saída.

## 3. Testar acesso e geração

Primeiro consulte os modelos, no mesmo ambiente de rede do backend. No PowerShell, na raiz do projeto com dependências instaladas, carregue a configuração sem exibir a chave:

```powershell
$apiKey = & .\.venv\Scripts\python.exe -c "from backend.config import settings; print(settings.baro_api_key)"
$baseUrl = & .\.venv\Scripts\python.exe -c "from backend.config import settings; print(settings.base_url)"
if (-not $apiKey) { throw "Preencha BARO_API_KEY no .env local antes de testar." }
Invoke-RestMethod -Uri "$baseUrl/models" -Headers @{ Authorization = "Bearer $apiKey" } -TimeoutSec 15
```

A resposta deve listar `google/gemma-3-27b`. Isso comprova acesso ao catálogo naquele momento, não comprova que a geração funciona. Para testar a geração, no mesmo **PowerShell**, mantendo as variáveis acima:

```powershell
$body = @{
    model = "google/gemma-3-27b"
    messages = @(@{ role = "user"; content = "Responda apenas: conexao funcionando." })
    max_tokens = 64
    stream = $false
} | ConvertTo-Json -Depth 5

$result = Invoke-RestMethod `
    -Method Post `
    -Uri "$baseUrl/chat/completions" `
    -Headers @{ Authorization = "Bearer $apiKey" } `
    -ContentType "application/json" `
    -Body $body `
    -TimeoutSec 120

$result.choices[0].message.content
```

Os comandos leem URL e chave do `.env` local. Atualize esse arquivo se o professor fornecer outro endpoint ou uma nova chave. Não exiba `$apiKey`, não compartilhe o conteúdo do `.env` e não cole os colchetes de um link Markdown no terminal.

## 4. Rodar e conferir o chatbot

Na instalação local que já possui Python virtual e Node portátil em `../.tools`:

```powershell
.\start-local.cmd
```

Abra http://127.0.0.1:5173, entre na conta e teste uma pergunta e uma continuação. Em um PC novo sem o ambiente portátil, siga a [instalação manual](02%20-%20Migracao%20para%20outro%20PC.md): backend e frontend em terminais separados. `start-local.cmd` não instala dependências nem libera redes.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
```

`configured=true` só confirma configuração presente; não é um teste de conectividade com a Mauá. `analytics_ready=true` confirma a presença do arquivo analítico, não a integridade de todos os dados. Valide o catálogo, a geração e o chat.

Para reiniciar após mudar o `.env`:

```powershell
.\stop-local.cmd
.\start-local.cmd
```

Mudar de Wi-Fi não exige trocar URL, modelo ou banco. Se perder acesso, repita o diagnóstico de IP e a consulta de modelos. O histórico continua no mesmo navegador e os arquivos de memória permanecem na mesma instalação. Outro PC não recebe esses arquivos automaticamente pelo Git.

## 5. Backend na nuvem

Para independência do IP residencial, hospede o backend em um ambiente com saída estável e autorizada pelo responsável. Valide o IP **de saída**, inclusive se houver NAT; um IP reservado para entrada ou um domínio DNS não garante a saída correta. Não existe promessa de IP gratuito ou permanente para sempre: depende do provedor, contrato e manutenção.

No Render, a saída padrão pode usar qualquer IP das faixas compartilhadas da região. Consulte **Connect > Outbound** no serviço e combine com o professor se ele aceita essas faixas. Não peça liberação somente de um IP observado em um teste nem recomende liberar uma faixa compartilhada sem avaliar quem mais a utiliza. [Documentação de saída do Render](https://render.com/docs/outbound-ip-addresses).

IPs dedicados de saída no Render exigem plano compatível e cobrança adicional; não trate essa opção como gratuita. Confira as condições atuais antes de contratar. [Documentação de IPs dedicados](https://render.com/docs/dedicated-ips).

VPN institucional só ajuda se for autorizada e se a rota até a IA realmente sair pela rede liberada. DDNS, mudar o IP privado do Windows e um túnel que apenas publica o backend não resolvem, por si só, a autorização do IP de saída.

Antes de publicar: HTTPS, JWT forte, `SEED_TEST_USERS=false`, remoção das contas de demonstração existentes, `APP_ENVIRONMENT=production`, CORS restrito, controle de acesso e consumo, persistência e backups dos bancos. Não exponha as portas locais de desenvolvimento na internet. Veja [deploy e segurança](01%20-%20Deploy%20e%20IP%20fixo.md).

## Diagnóstico rápido

| Sintoma | Conferir |
|---|---|
| Modelos retornam 401/403 | Cabeçalho, autorização e IP efetivamente visto pelo servidor; confirmar com o professor |
| Timeout ou conexão recusada | Rota, firewall, disponibilidade da API, autorização e fila do modelo; não atribuir automaticamente ao IP |
| Catálogo funciona, geração falha | Modelo disponível, resposta HTTP, tamanho do pedido e disponibilidade do servidor |
| Chat dá 401, mas teste direto funciona | Sessão JWT da aplicação: fazer login novamente |
| Site abre, login falha | Backend, banco de usuários, URL do frontend e CORS |
| Resposta informa cálculo local | A interpretação do modelo falhou; os cálculos locais não provam acesso ao Gemma |
| Parou ao trocar de Wi-Fi ou reiniciar modem | Medir saída novamente e confirmar autorização; não trocar a Base URL pelo IP de casa |
| Funciona no terminal, não no serviço | Comparar proxy, VPN, ambiente/container, `.env` e rota do processo do backend |

Nunca use `0.0.0.0/0` como solução para liberar acesso à IA. A autorização deve permanecer limitada às origens aprovadas.
