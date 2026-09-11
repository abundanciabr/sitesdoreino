# Auditoria independente da medição Pareto do capítulo 1

Data da auditoria: 2026-09-11

Tarefa: TAR-348

Auditor: sessão `sessao-painel-auditoria-pareto-capitulo1`

Entrega auditada: TAR-338, PR #1561

## Veredito

**O instrumento publicado é válido para iniciar a coleta, mas não existe
amostra confirmatória.** A entrada contém cinco eventos estruturalmente
válidos e nenhum evento que satisfaça o contrato confirmatório. Portanto, a
amostra é insuficiente, a avaliação comparativa é inconclusiva e nenhuma
expansão está autorizada.

O estado `em coleta` impresso pelo analisador descreve a ausência de unidades
elegíveis. Ele não representa benefício zero, regressão zero nem conclusão de
eficiência. As tarefas TAR-338 e TAR-348 são correção e auditoria do
instrumento, por isso não entram na própria amostra.

## Identidade do material auditado

| Item | Resultado conferido |
|---|---|
| Protocolo | `docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md`, congelado no commit `900c7481265b65d39db3b62ba396e4c4f4f0763f` |
| Cabeça do PR #1561 | `f0c85e1ee23a1e27486f2b35b1ad5cf8b7e013ed` |
| Merge publicado | `98fccb36d0550e18a2a6c6877c743fa2aa7eaee8` |
| Entrada privada completa | SHA-256 `d4f1d527f4ae68b59d0f707216faf39df1adc62237be564856be2921ca8e7c56` |
| Revisão composta do instrumento | `8cdc4905084d1d5c68745523897edf36367d6b7d` |
| Revisão do analisador | SHA-256 `62f318c5aa70b7d9a1769c989824c50af71b13a161b1af1ac6b5c0fb6c6ca5e0` |
| Fonte | `.git/telemetria-dos-robos/*.jsonl`, privada e não publicada |

A revisão composta foi recalculada com os quatro textos versionados declarados
pelo instrumento: registrador, telemetria, analisador e protocolo. A revisão
do analisador foi calculada diretamente do texto UTF-8. O hash da entrada foi
calculado sobre a lista integral dos eventos `tarefa_medida`, com chaves
ordenadas, sem publicar o conteúdo bruto.

## Recálculo independente

O recálculo versionado em `ci/auditar_medicao_fase4.py` usou somente a
biblioteca padrão para percorrer os arquivos JSONL, recompor a identidade
SHA-256 de cada evento e conferir fonte, estado, relógios com fuso e métricas
não negativas. Ele não importou `ci/analise_fase4.py`,
`ci/registrar_tarefa_fase4.py`, `ci/telemetria.py` nem suas funções
decisórias. O teste `ci/tests/test_auditar_medicao_fase4.py` inspeciona a
árvore sintática dos imports, fixa as revisões publicadas e sabota remoção,
estado e métrica nula.

| Medida | Resultado |
|---|---:|
| Eventos `tarefa_medida` | 5 |
| Eventos estruturalmente válidos | 5 |
| Eventos no esquema confirmatório 2 | 0 |
| Eventos confirmatórios completos | 0 |
| Tarefas elegíveis | 0 |
| Pares declarados ou elegíveis | 0 |
| Métricas explicitamente nulas | 54 |

Os cinco eventos pertencem a quatro tarefas reais: TAR-280, TAR-291, TAR-324
e TAR-339. TAR-280 tem duas transições da mesma tentativa, que não viram duas
unidades. Todos usam o formato anterior ao esquema 2, sem tarefa versionada,
classificação anterior, vínculo integral ou evidência de resultado. Essa
validade estrutural preserva o histórico, mas não autoriza promover nenhuma
linha à coorte confirmatória.

Como o conjunto confirmatório está vazio, não existe tupla de evento para
conferir contra ancestralidade e estado remoto. A auditoria tratou essa
ausência como zero candidatos, não como aprovação implícita. A cadeia publicada
do instrumento foi conferida separadamente: a cabeça do PR #1561 é ancestral
do merge, o merge é ancestral desta bancada, e o GitHub informa o PR como
`MERGED`.

## Publicação conferida

O deploy `34602581463` corresponde ao merge
`98fccb36d0550e18a2a6c6877c743fa2aa7eaee8` e terminou
`completed/success`. Os quatro jobs `detectar`, `portao-de-deploy`,
`publicar-dados-admin` e `deploy (admin)` terminaram com sucesso. Nenhuma prova
exigida apareceu ausente ou pulada.

## Correspondência com o protocolo

| Regra | Resultado da auditoria |
|---|---|
| Unidade é tarefa, não evento ou retomada | Atendida; nenhuma unidade foi formada sem confirmação e a dupla da TAR-280 não foi contada |
| Classificação anterior ao resultado | Sem observação confirmatória; os cinco eventos antigos não carregam essa prova |
| Ausência não vira zero | Atendida; 54 métricas continuam nulas |
| Fixture não mede produtividade | Atendida; não há fonte sintética entre os cinco eventos |
| Falha e abandono não somem | Atendida pelo instrumento; não há evento confirmatório desse tipo nesta entrada |
| Vinte tarefas por condição e dez pares | Não atendida; a amostra elegível está vazia |
| Auditoria antes da expansão | Atendida para estes hashes; a expansão continua não liberada |

## Comandos e saídas observadas

```text
python -m pytest ci/tests/test_analise_fase4.py ci/tests/test_registrar_tarefa_fase4.py ci/tests/test_metricas_percurso.py -q
90 passed in 1.70s

python ci/analise_fase4.py --local
instrumentacao: implementada
amostra_disponivel: ausente
avaliacao: em coleta
eventos_estruturalmente_validos: 5
tarefas_confirmatorias_completas: 0
tarefas_validas: 0
tentativas_validas: 0
entrada_sha256: d4f1d527f4ae68b59d0f707216faf39df1adc62237be564856be2921ca8e7c56

python ci/auditar_medicao_fase4.py --local
estado: PASS
entrada_sha256: d4f1d527f4ae68b59d0f707216faf39df1adc62237be564856be2921ca8e7c56
revisao_instrumento: 8cdc4905084d1d5c68745523897edf36367d6b7d
revisao_analise: 62f318c5aa70b7d9a1769c989824c50af71b13a161b1af1ac6b5c0fb6c6ca5e0
eventos_tarefa_medida: 5
eventos_estruturalmente_validos: 5
candidatos_confirmatorios_schema2_encerrados: 0
tarefas_confirmatorias_completas: 0
tarefas_distintas: 4
pares_declarados_ou_elegiveis: 0
metricas_ausentes_nao_convertidas_em_zero: 54

python -m pytest ci/tests/test_auditar_medicao_fase4.py -q
5 passed in 0.21s

git merge-base --is-ancestor f0c85e1ee23a1e27486f2b35b1ad5cf8b7e013ed 98fccb36d0550e18a2a6c6877c743fa2aa7eaee8
exit 0

gh run view 34602581463 --json status,conclusion,headSha,event,name,url
status=completed conclusion=success headSha=98fccb36d0550e18a2a6c6877c743fa2aa7eaee8
```

## Decisão operacional

TAR-348 pode ser submetida como a auditoria independente desta entrada e
destas revisões. O instrumento permanece apto para coletar tarefas novas que
sejam classificadas antes do início e encerradas com evidência. A avaliação
continua inconclusiva até existirem 20 tarefas elegíveis por condição, pelo
menos 10 pares compatíveis, qualidade completa e custo observado. Nenhuma
expansão foi autorizada.
