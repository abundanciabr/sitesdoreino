# Protocolo da Fase 4, medição dos pilotos

Data de congelamento: 2026-09-08

Este protocolo é anterior à análise confirmatória. A fonte de eventos é o
caderninho privado de `ci/telemetria.py`; a análise é executada por
`ci/analise_fase4.py`. Nenhum resultado deste documento autoriza preencher
dados ausentes por estimativa.

## Pergunta e unidade

A pergunta é se o mecanismo piloto reduz o trabalho total de uma entrega
verificada sem transferir custo para revisão, adoção, manutenção ou falhas.

A unidade principal é uma tarefa legítima ou uma correção transversal. Uma
tarefa conserva a relação entre tentativa, execução, revisão, integração e
resultado. PR, commit, chamada ou job não são unidades independentes.

## Pilotos e condições

| Piloto | Condição antes | Condição depois | Unidade | Resultado exigido |
|---|---|---|---|---|
| Fase 1 | percurso anterior à abertura, contexto e fechamento corrigidos | percurso da revisão instrumentada | tarefa de agente | resultado verificado |
| Fase 2 | publicação de dados pelo caminho anterior | publicação sem rebuild e sem reinício, quando aplicável | correção de dados | dado observado no consumidor |
| Fase 3 | implementações locais equivalentes separadas | `outbox-relay` versionado adotado | correção transversal e adoções | adoção publicada e jornada verificada |

Cada evento recebe piloto, condição, tipo, complexidade, revisão do
instrumento, fonte, revisão do código e os atributos de elegibilidade. Uma
retomada permanece na mesma tarefa e tentativa, não cria observação nova.
O analisador consolida as tentativas da mesma tarefa antes de contar a amostra
e soma somente métricas explicitamente observadas. Uma classificação alterada
entre tentativas torna o pareamento incompatível.

## Elegibilidade e comparabilidade

Entram tarefas consecutivas que tenham sido classificadas antes do resultado
por natureza da alteração, componentes, fronteiras de integração, migração,
risco, validações e escopo de publicação. Antes e depois devem usar a mesma
versão do instrumento ou uma revisão explicitamente comparada.

São exclusões declaradas: tarefa duplicada, ausência de identidade, tipo ou
complexidade ausente, revisão do instrumento não identificada, relógio sem
fuso, condição ausente e resultado ainda sem encerramento. Falhas, abandono e
pendências elegíveis não são apagados: entram na amostra e no custo; não
entram como tempo concluído.

## Amostragem e pareamento

O primeiro ponto de revisão tem 20 tarefas antes e 20 depois por piloto,
quando houver tarefas elegíveis reais. O relatório informa quantas chegaram,
quantas formam pares completos, quantas estão pendentes e cada exclusão.
Dez pares completos são o mínimo para uma leitura confirmatória pareada. Menos
que isso mantém o resultado inconclusivo.

O pareamento usa `par_id` definido antes de observar o resultado. Quando o
pareamento não for legítimo, a análise informa a estratificação por tipo e
complexidade, sem tratar tarefas diferentes como pares artificiais.

## Métricas

A métrica principal é a mediana, em minutos, do início da preparação
operacional até o resultado exigido e verificado. O relógio não começa depois
do contexto e não termina antes da publicação ou da observação prevista.

São secundárias: chamadas de modelo identificadas, chamadas de ferramenta,
contexto em bytes, runner em minutos, retentativas, correções de revisão,
reaberturas, falhas, abandono, defeitos escapados, violações de segurança,
minutos de adoção e minutos de manutenção.

O custo completo em minutos soma tempo observado da tarefa, adoção e
manutenção. Totais de chamadas e de runner são apresentados separadamente,
sem convertê-los em dinheiro ou tokens quando a fonte não permite isso.

## Regra de decisão

`benefício demonstrado no escopo` exige simultaneamente:

1. pelo menos 20 tarefas elegíveis em cada condição;
2. pelo menos 10 pares com duração válida;
3. a mesma revisão do instrumento na comparação;
4. qualidade e segurança observadas em todas as tarefas, sem violação ou
   defeito escapado;
5. mediana depois menor que a mediana antes, com o limite superior de 97,5%
   da reamostragem pareada ainda abaixo de zero;
6. custo completo depois menor que o custo completo antes, incluindo adoção
   e manutenção.

O intervalo é descritivo, obtido por 2.000 reamostragens pareadas com semente
fixa. Não há valor-p e ele não decide sozinho. Sem cobertura suficiente, o
resultado é inconclusivo ou não avaliável. Piora relevante ou violação
obrigatória é regressão. Uma melhoria aparente sem dados completos não libera
expansão.

## Qualidade, segurança e expansão

Os testes determinísticos críticos continuam obrigatórios. A expansão fica
suspensa se houver perda, duplicação, isolamento quebrado, autorização
violada, publicação incompatível, aprovação sem prova ou semântica de erro
alterada.

Mesmo com benefício demonstrado, a Fase 3 só pode expandir depois de a
adoção nas duas consumidoras iniciais, a qualidade, o custo, a recuperação e
a auditoria independente estarem comprovados. O lote seguinte é pequeno,
com versão fixada por consumidora e jornada real verificada.

Clientes gerados não entram nesta análise antes dessa condição de entrada. Se
ela não for atendida, o estado é avaliação não liberada.

## Auditoria e retomada

O auditor independente recebe a revisão do protocolo, o conjunto anonimizável,
os eventos brutos autorizados, o hash da entrada, a revisão do analisador e
os comandos. Ele recalcula medianas, intervalos, custos, exclusões e estados
de qualidade. Mudança de código, instrumento ou protocolo invalida a análise
afetada e exige novo cálculo.

Comandos operacionais:

```text
python ci/registrar_tarefa_fase4.py --manifesto <arquivo-json-da-tarefa>
python ci/analise_fase4.py --local
python -m pytest ci/tests/test_analise_fase4.py ci/tests/test_metricas_percurso.py -q
```

O primeiro comando recebe um manifesto JSON com todos os campos da identidade,
relógios e todas as métricas. Cada métrica precisa aparecer com um valor
observado ou `null`; o comando não cria zero por ausência. O estado `pendente`
pode ter `fim: null`, enquanto qualquer estado encerrado exige fim com fuso.
O segundo comando lê somente o `.git` comum e imprime o JSON. O terceiro testa
deduplicação, ausência, cobertura, cálculo, decisão e regressão. Não se criam
tarefas ou pares artificiais para atingir o alvo.
