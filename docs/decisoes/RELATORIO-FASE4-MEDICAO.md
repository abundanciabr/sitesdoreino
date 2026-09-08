# Relatório da Fase 4, coleta operacional e avaliação comparativa

Data da análise: 2026-09-08

## A. Veredito

**Estado global: NÃO PRONTA.** A coleta operacional foi demonstrada em uma
tarefa real já autorizada. A avaliação comparativa continua inconclusiva,
porque existe uma observação depois, nenhuma observação antes e nenhum par.
A auditoria independente da entrada atual foi concluída e confirmou essa
limitação.

Na abertura desta retomada, a saída confundia instrumentação implementada com
amostra disponível. A distinção agora é explícita: `instrumentacao:
implementada` informa que o caminho escreve e lê a unidade Fase 4;
`amostra_disponivel` informa se há observações reais elegíveis. Depois da
execução de TAR-280, há uma tarefa real reconhecida, mas a avaliação continua
inconclusiva por não haver condição antes nem par válido.

O cenário controlado da TAR-282 continua fora da produtividade operacional.
Os seus 17 testes verdes comprovam as regras do analisador, mas não entram no
caderno privado e não formam amostra.

## B. Fontes, período e diagnóstico da entrada

Fontes consultadas:

- `ci/telemetria.py`, leitor e registrador do instrumento;
- `.git/telemetria-dos-robos/*.jsonl`, 199 arquivos privados;
- `ci/analise_fase4.py`, revisão da análise `fase4-2026-09-08-2`;
- protocolo em `docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md`;
- parecer em `docs/decisoes/AUDITORIA-INDEPENDENTE-FASE4-20260908.md`;
- fila, reserva e evento de execução da TAR-280;
- PR #1420, auditoria independente da entrada atual;
- testes focais do analisador, do registrador e do percurso.

Período considerado: 2026-08-30T01:41:24Z a 2026-09-08T21:28:34Z.
Revisão do instrumento registrada na tarefa: `bbe1036d0f8fb5b3e434fe36bc57ab7eee2f810e`.
Hash da entrada usada na análise: `44cef42c07ac6c5e8325cab0e512a71aa8bd56e722f9df9b9dc4619d8bf9025c`.

| Categoria | Quantidade | Interpretação |
|---|---:|---|
| Registros encontrados | 2.519 | Todas as linhas legíveis do caderno privado |
| Registros `tarefa_medida` | 2 | Abertura e fechamento da mesma TAR-280 |
| Tarefas consolidadas | 1 | A repetição não virou tarefa nova |
| Sintéticos excluídos | 0 na fonte real | O teste que prova a exclusão passou; fixture não entra no caderno |
| Reais reconhecidos | 2 registros, 1 tarefa | Fonte `registro-operacional-autorizado` |
| Reais inelegíveis pelo protocolo | 0 | Nenhum registro real foi rejeitado por elegibilidade |
| Reais incompletos | 0 | O estado pendente é válido quando o início existe e o fim ainda não existe |
| Erros de leitura | 0 | 0 arquivos ilegíveis e 0 linhas inválidas |
| Erros de correlação ou validação | 0 | Nenhum `tarefa_medida` real foi recusado por identidade |
| Históricos de outras fases ou formatos | 2.517 | Não carregam o contrato completo da Fase 4 |

O diagnóstico diferencia os cinco casos pedidos. Não houve caso A de caderno
vazio: houve leitura de histórico. O caso B foi demonstrado nos testes, com a
fonte sintética excluída antes da amostra. Os casos C e E foram zero. A abertura
pendente foi preservada como tentativa da mesma tarefa, e as métricas ausentes
ficaram nulas sem virar zero.

## C. Tarefa real acompanhada

| Campo | Valor conferido |
|---|---|
| Tarefa | TAR-280, coleta e análise de tarefas reais comparáveis da Fase 4 |
| Autorização | Fila, livre antes da execução, reivindicada por esta sessão |
| Piloto e condição | Fase 1, depois |
| Tentativa | `sessao-ci-retomar-fase4-coleta-real` |
| Reserva | `tarefa-TAR-280` |
| Instrumento | revisão `bbe1036d0f8fb5b3e434fe36bc57ab7eee2f810e` |
| Eventos | uma abertura pendente e um fechamento concluído |
| Resultado exigido | testes focais verdes, análise reproduzida e tabela de amostra |
| Publicação | não aplicável nesta tarefa; não houve consumidor novo |

O cenário foi executado no fluxo normal da fila. A cadeia comprovada foi:

```text
fonte operacional da TAR-280
  -> dois registros tarefa_medida reconhecidos
  -> mesma tarefa e tentativa consolidadas
  -> fechamento concluído com duração observada
  -> uma observação depois na Fase 1
```

A observação inicial pendente permaneceu registrada. A consolidação não a
transformou em tarefa adicional. Como as métricas de custo foram nulas na
abertura, o custo completo depois permanece indisponível. Isso impede uma
conclusão de benefício e preserva o custo desconhecido.

## D. Matriz F4-01 a F4-12

| Critério | Estado efetivo | Evidência | Pendência |
|---|---|---|---|
| F4-01 Prontidão dos pilotos | parcial | Fases 1, 2 e 3 têm revisões e publicações históricas identificadas | jornada comparável por piloto |
| F4-02 Instrumentação | atendido para coleta ponta a ponta | TAR-280 reconhecida e consolidada; fonte e revisão aparecem no relatório | mais tarefas operacionais |
| F4-03 Protocolo | atendido | protocolo congelado antes da análise, revisão `fase4-2026-09-08-2` | nenhuma |
| F4-04 Identidade e deduplicação | atendido neste caso | 2 tentativas observadas, 1 tarefa consolidada, retomada preservada | repetir em outras tarefas |
| F4-05 Amostra e cálculo | parcial | Fase 1: depois 1, antes 0, pares 0; Fases 2 e 3: 0 | 20 por condição e 10 pares válidos |
| F4-06 Qualidade e segurança | parcial | testes cobrem ausência, falha, dado ausente e violação | observações operacionais completas |
| F4-07 Custo completo | parcial | duração depois observada; custo completo nulo por métricas ausentes | adoção, manutenção e custos de todas as tarefas |
| F4-08 Comparabilidade | parcial | Fase 1 e condição depois reconhecidas; nenhuma comparação formada | condição antes e atributos comparáveis |
| F4-09 Não executar sem liberação | atendido | nenhum consumidor novo alterado ou expandido | manter bloqueio |
| F4-10 Condição de entrada | não liberada | não há benefício comparativo nem qualidade operacional completa | amostra, qualidade, recuperação e auditoria |
| F4-11 Auditoria | atendido para a entrada atual | parecer independente reproduziu a análise, conferiu o hash e retestou os critérios | auditar novamente após novas observações |
| F4-12 Separação de implementação, execução e publicação | atendido no relatório, parcial no ciclo | custos desconhecidos não viraram zero; publicação não foi alegada | revisão, PR e publicação do relatório |

## E. Amostra por piloto e condição

| Piloto | Antes | Depois | Pares válidos | Pendências | Falhas ou abandono | Exclusões comparativas |
|---|---:|---:|---:|---:|---:|---:|
| Fase 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| Fase 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| Fase 3 | 0 | 0 | 0 | 0 | 0 | 0 |

Há uma observação com tempo na condição depois da Fase 1. Não há linha de
base antes, pareamento, mediana comparável ou intervalo de diferenças. A
frase correta é: **Coleta operacional demonstrada neste caso; avaliação
comparativa ainda em andamento.**

## F. Linha de base e custo da instrumentação

Linha de base confirmatória disponível: nenhuma. O histórico do percurso tem
42 tarefas, 89 tentativas e 310 eventos correlacionados, mas a cobertura é
global, faltam as fases de revisão, integração e publicação, e nenhum evento
histórico tem o contrato completo da Fase 4. Ele não foi convertido em linha
de base fictícia.

O custo da implementação e validação foi mantido separado da produtividade:

- TAR-282 ficou fora da amostra operacional;
- os testes focais desta retomada registram a validação do instrumento,
  não ganho de piloto;
- a TAR-280 é identificada como coleta operacional autorizada, não como
  comparação de eficiência geral;
- chamadas, adoção, manutenção e outros custos sem fonte foram mantidos
  como nulos, não como zero;
- não houve publicação ou consumidor novo para declarar.

## G. O que os dados permitem concluir

Permitem concluir que uma tarefa real da fila foi registrada pelo comando
operacional, que a retomada foi preservada na mesma tarefa, que o fechamento
foi reconhecido e que a consolidação não duplicou a amostra. Permitem também
concluir que o cenário sintético é excluído pelos testes e que a leitura atual
não tem erro de arquivo, correlação ou validação.

Não permitem concluir ganho, regressão, economia, comparabilidade, linha de
base, custo completo ou expansão. Não há 20 observações em cada condição, 10
pares ou qualidade operacional completa. A auditoria independente confirmou
essa conclusão.

## H. Auditoria independente

O parecer de `TAR-281` foi executado em contexto e bancada separados da coleta,
reproduziu a análise, recalculou os resultados principais, conferiu o hash da
entrada e verificou as exclusões. O PR #1420 foi incorporado com checks verdes
e o deploy `34283078065` terminou com `completed/success`.

Os achados independentes confirmam três bloqueios médios: amostra insuficiente,
qualidade e custo incompletos, e percurso sem prova de publicação. Também
confirmam que a fonte sintética não contaminou a amostra e que a retomada da
TAR-280 não duplicou a tarefa.

TAR-281 está concluída como auditoria da entrada atual. Ela não libera
expansão, não cria amostra artificial e não transforma ausência em zero. Novas
observações exigem nova análise e nova auditoria antes de qualquer decisão de
expansão.

## I. Comandos e saídas reais

```text
python -m pytest ci/tests/test_pr.py ci/tests/test_analise_fase4.py ci/tests/test_registrar_tarefa_fase4.py ci/tests/test_fila.py ci/tests/test_sessao.py -q
339 passed in 79.40s

python ci/registrar_tarefa_fase4.py --manifesto medicao-tar280.json
PASS tarefa registrada: id=c4902a38e2edd7578518281be355ebd3a0fb17d5420eae5b0e5b8de53043a92a

python ci/analise_fase4.py --local
instrumentacao: implementada
amostra_disponivel: disponível
avaliacao: inconclusiva
registros_encontrados: 2519
registros_tarefa_medida: 2
tarefas_validas: 1
tentativas_validas: 2
fase1 antes=0 depois=1 pares=0 custo_completo_depois=indisponivel
fase2 antes=0 depois=0 pares=0
fase3 antes=0 depois=0 pares=0
entrada_sha256: 44cef42c07ac6c5e8325cab0e512a71aa8bd56e722f9df9b9dc4619d8bf9025c
```

## J. Próximas condições, sem fabricar amostra

1. Continuar registrando tarefas normais elegíveis antes do início e no
   fechamento, sem usar TAR-282 como produtividade.
2. Formar condições antes e depois comparáveis, com custo completo e qualidade
   observada.
3. Manter a expansão bloqueada e repetir a auditoria depois de novas
   observações reais comparáveis.
4. Recalcular a análise antes de qualquer decisão de expansão.

## Conclusão global

**NÃO PRONTA.** A coleta operacional foi demonstrada neste caso e a auditoria
independente foi concluída. A avaliação comparativa ainda está em andamento e
não há ganho comprovado.
