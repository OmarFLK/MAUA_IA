# Dicionário dos relatórios SEMOB

## Operação diária

Contém data de serviço, dia da semana, quantidade de veículos, máximo de veículos por faixa, viagens programadas, viagens realizadas, diferença de viagens e quilometragens produtiva, improdutiva e total.

Quilometragem produtiva é a distância registrada como parte produtiva da operação. Quilometragem improdutiva é a distância operacional registrada fora da parcela produtiva. Quilometragem total é a soma dessas duas parcelas no relatório.

## Viagens e exceções

Os registros de viagem incluem linha, prefixo do veículo, atividade, sentido, faixa horária, início e fim realizados e quilometragem. Os relatórios de exceção incluem ocorrências não iniciadas, não realizadas ou não terminadas, com horários programados e realizados quando disponíveis.

Uma linha ausente de um relatório de exceções não deve ser interpretada automaticamente como operação perfeita. A conclusão deve considerar a cobertura do arquivo, o tipo de exceção e o período consultado.

## Passageiros

Os relatórios diários distinguem passageiros de catraca, antecipados, não pagantes e total de passageiros. Totais publicados no rodapé não entram na camada canônica; o total analítico é recalculado a partir dos dias normalizados.

Para análise, `passageiros_pagantes` é uma métrica derivada calculada como `Catraca + Antecipados`. A consistência com `Total Passageiros - Não Pagantes` deve ser verificada na auditoria local de cada conjunto. A interpretação de negócio ainda deve ser homologada formalmente pela SEMOB; por isso as respostas identificam a métrica como derivação operacional, e não como classificação institucional definitiva.

## Bilhetagem e saldos

Os relatórios financeiros possuem créditos transferidos para cartões, saldo final, total de vendas, total de utilização e crédito circulante. Valores monetários são convertidos da notação brasileira para número decimal, preservando a origem.
