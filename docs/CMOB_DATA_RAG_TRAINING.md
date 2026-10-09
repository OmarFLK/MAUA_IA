# CMob: dados, RAG e preparacao de fine-tuning

## O que foi executado

44 HTMLs foram analisados em 10 tabelas, com datas ISO, numeros brasileiros
convertidos sem separadores de milhar, codigos preservados como texto,
precedencia para evitar sobreposicao de mensal/quinzenal e origem por registro.
Foram publicados 107.867 registros em CSV e um resumo mensal separado. Os
originais locais nao sao publicados; identificacao do motorista foi removida.
O manifesto registra os hashes dos HTMLs/CSVs, contagens, cobertura e alertas.
O codigo nao preenche lacunas com valores estimados nem corrige a fonte em silencio.

## DuckDB e nuvem

DuckDB e um motor SQL analitico embutido: le os CSVs e guarda tabelas num arquivo,
sem instalar um servidor de banco. Consultas autorizadas calculam os numeros;
o Gemma interpreta as evidencias, sem receber o arquivo inteiro de viagens.
GitHub versiona os CSVs (~23 MB). O build Docker verifica SHA-256 e tipos e
reconstroi o DuckDB no Render. Isso evita depender do disco temporario para
preservar o snapshot: cada deploy contem a mesma versao. O Neon mantem o banco
transacional de usuarios/conversas. Dados novos nao entram automaticamente.
Para volumes maiores ou atualizacao frequente, migrar os snapshots para object
storage e publicar um manifesto versionado; nao e necessario nesta entrega.

## RAG executado

Documentos em `knowledge/generated` descrevem tabelas, campos, cobertura e
agregados verificados, junto do dicionario/regras ja existentes. O indice SQLite
segmenta esses documentos e busca com FTS5/BM25 e vetores de hashing de tokens.
Nao e um modelo de embeddings aprendido: e recuperacao lexical/hashing local.
O backend insere os trechos recuperados no contexto das respostas conceituais.
Perguntas quantitativas seguem para planos SQL validados no DuckDB. Seguir o
contexto da conversa nao exige repetir SEMOB em toda pergunta.

## Fine-tuning: preparado, NAO executado

`data/finetuning` contem 517 exemplos de treino e 121 de validacao. As respostas
usam resultados reais do backend, incluindo ausencia de registros e continuacoes
como "preciso de mais detalhes em todos os sentidos por favor". O split e
temporal: julho/agosto no treino, setembro exclusivamente na validacao.
Os exemplos foram gerados automaticamente e exigem revisao humana. Nao sao
evidencia de melhora do modelo. `manifest.json` declara `trained: false`.

Fine-tuning muda pesos do modelo; RAG apenas fornece contexto a um modelo sem
mudar seus pesos. QLoRA treina adaptadores pequenos sobre uma base quantizada
em 4 bits, nao ensina o modelo a manter numeros mensais atualizados. O objetivo
do candidato e comportamento analitico fundamentado, nao memorizar tabelas.
Referencia: [guia oficial Google](https://ai.google.dev/gemma/docs/core/huggingface_text_finetune_qlora).

Nao ha pesos locais do Gemma nem ambiente CUDA disponivel nesta maquina AMD.
O Render atual executa a API, nao treina/carrega o Gemma 27B. O acesso Baro de
inferencia tambem nao autoriza alterar os pesos do modelo remoto. E necessario
obter do responsavel a revisao/tokenizer exatos, aceitar a licenca dos pesos e
disponibilizar GPU para treinamento e posterior hospedagem do adaptador.
[Modelo oficial e licenca](https://huggingface.co/google/gemma-3-27b-it).

Receita preparada em `scripts/train_qlora.py`: Gemma3ForConditionalGeneration,
NF4, LoRA nas camadas de linguagem, perda apenas na ultima resposta, validacao
por epoca, salvamento de tokenizer/adaptador e manifesto apos treino bem-sucedido.
Nao foi validada em GPU. O limite de 24 GB e somente uma barreira minima,
nao uma garantia de que 27B/4096 tokens cabem; testar memoria antes do treino.
Nenhum custo de GPU, download de pesos ou novo servico foi contratado.

```sh
python -m scripts.ingest_semob
python -m scripts.publish_cmob_data
python -m scripts.build_cmob_data
python -m scripts.index_documents
python -m scripts.prepare_finetuning
```

Depois de revisar o dataset, executar a receita num ambiente GPU dedicado,
instalando `requirements-training.txt` e indicando o diretorio real dos pesos
licenciados com `--model`. Avaliar factualidade, recusas indevidas, seguimento
de contexto e numeros antes de qualquer ativacao. Nenhum adaptador foi ativado;
Gemma Livre continua sem RAG ou fine-tuning CMob.

## API pronta para o futuro dashboard

Nao foi criado um tunel publico ou liberado acesso sem autenticacao.
O futuro dashboard pode usar os endpoints ja autenticados por JWT:

- `GET https://cmob-ai-backend.onrender.com/api/semob/catalog`: versao, tabelas,
  metricas/unidades e cobertura por mes; sem expor expressoes SQL internas.
- `POST https://cmob-ai-backend.onrender.com/api/semob/query`: QueryPlan validado,
  numeros estruturados, filtros e cobertura. Nao aceita SQL arbitrario.
- `POST https://cmob-ai-backend.onrender.com/api/chat`: mensagens, `assistant:
  "cmob"`, `conversation_id` por conversa, stream NDJSON.
- `GET https://cmob-ai-backend.onrender.com/api/health`: disponibilidade.
- `GET https://cmob-ai-backend.onrender.com/api/ready`: banco transacional.

O frontend ativo e https://maua-ia.vercel.app. A integracao com outro dashboard
permanece nao usada; quando existir, configurar sua origem CORS e sua estrategia
de identidade. Nenhuma chave Baro/Neon/JWT deve ir para o navegador ou GitHub.
