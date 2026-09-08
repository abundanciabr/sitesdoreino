# Relatório da Fase 4, medição verificável dos pilotos

Data da análise: 2026-09-08

## A. Veredito

**Estado global: PARCIAL.** A instrumentação, o protocolo, o analisador e os
testes foram implementados na bancada. A análise real não encontrou tarefas
com o novo contrato de medição. Não há comparação confirmatória, auditoria
independente ou expansão liberada.

| Estado | Resultado |
|---|---|
| Instrumentação | implementada na bancada com comando operacional fail-closed, ainda não publicada |
| Avaliação | em coleta, sem base comparável |
| Fase 1 | não avaliável para eficiência |
| Fase 2 | não avaliável para eficiência |
| Fase 3 | não avaliável para eficiência |
| Qualidade | testes determinísticos do instrumento atendidos; qualidade operacional sem evidência comparável |
| Expansão | bloqueada, condição de entrada não atendida |
| Auditoria | autoauditoria executada; independente pendente |
| Publicação | pendente para esta entrega |

## B. Matriz F4-01 a F4-12

| Critério | Implementação | Prova | Resultado | Pendência |
|---|---|---|---|---|
| F4-01 | matriz de estado e dependências neste relatório | `gh pr view` e `gh run view` dos PRs 1382, 1385, 1386 e 1388 | atendido para o estado dos pilotos | jornada comparável ainda não coletada |
| F4-02 | `registrar_tarefa` reutiliza `ci/telemetria.py` | 129 testes focais verdes | atendido no instrumento e no comando operacional | uso por tarefas reais |
| F4-03 | protocolo congelado antes da análise | `PROTOCOLO-FASE4-MEDICAO.md` e revisão `fase4-2026-09-08-1` | atendido | nenhuma |
| F4-04 | identidade por tarefa, tentativa, revisão e fonte | teste de deduplicação e hash da entrada | parcialmente atendido | 0 tarefas reais no contrato novo |
| F4-05 | cálculo de amostra, pares, mediana e intervalo | saída do analisador com 0 tarefas válidas | não atendido | coleta antes e depois |
| F4-06 | guardas de qualidade, segurança e ausência | testes de dado ausente e violação | atendido para o método | janela operacional ainda vazia |
| F4-07 | custo completo e cobertura por campo | testes de custo ausente e saída nula | parcialmente atendido | minutos reais de falha, adoção e manutenção |
| F4-08 | classificação por piloto | saída `não avaliável` para os três pilotos | decisão correta de não liberar | base real comparável |
| F4-09 | não executada sem liberação | nenhum consumidor novo alterado | não aplicável, bloqueada | F4-05, F4-06 e auditoria |
| F4-10 | regra de condição de entrada documentada | protocolo declara avaliação não liberada | não liberada | benefício da Fase 3 não demonstrado |
| F4-11 | roteiro de reprodução documentado | hash da entrada e semente fixa | auditoria independente pendente | revisor com execução separada |
| F4-12 | relatório separa implementação, execução e publicação | estados deste documento | parcial | integração e publicação desta entrega |

## C. Estado das fases anteriores

| Piloto | Revisão efetivamente usada | Prontidão | Dependência |
|---|---|---|---|
| Fase 1 | PR 1382, merge `2097d490ef4c5846bc774534a33b17d8cea33c87`, deploy `34190915891` | instrumentação anterior integrada e publicada; eficiência não medida | tarefas com condição antes e depois |
| Fase 2 | PR 1385, merge `2ec7dbbd0fcd45e55f621638265db62b6e13fd80`, deploy `34241918302`; canário PR 1388, merge `f91ee3823ac7ad57d9faaf59e88c10199b7f7e80`, deploy `34243478861` | canário de publicação integrado e publicado | tarefas de dados com custo total e observação do consumidor |
| Fase 3 | PR 1386, merge `bf0b76d6744c011d75e5d75f2d295a449bf86c64`, deploy `34241181670` | pacote `outbox-relay==0.3.0` adotado em `alunos` e `identidade` | jornada real do outbox, adoções e custo comparável |

Os estados acima comprovam integração e publicação das fases anteriores. Não
comprovam redução de trabalho.

## D. Protocolo e amostra observada

| Piloto | Unidade | Antes | Depois | Pares | Pendentes | Exclusões |
|---|---|---:|---:|---:|---:|---:|
| Fase 1 | tarefa de agente | 0 | 0 | 0 | 0 | indisponível |
| Fase 2 | correção de dados | 0 | 0 | 0 | 0 | indisponível |
| Fase 3 | correção transversal e adoções | 0 | 0 | 0 | 0 | indisponível |

O analisador encontrou 2.183 eventos históricos, todos de outras fases ou do
formato anterior. Eles não foram convertidos retroativamente em tarefas Fase
4, porque não carregam condição, classificação e custo completos.

Não houve mudança de protocolo depois do resultado. A justificativa da
amostra inicial de 20 por condição e 10 pares mínimos está no protocolo, antes
da análise.

## E. Resultados

| Métrica | Antes | Depois | Diferença absoluta | Diferença relativa | Incerteza | Cobertura | Limitação |
|---|---|---|---|---|---|---|---|
| Mediana de minutos até resultado | indisponível | indisponível | indisponível | indisponível | indisponível | 0 tarefas | não há observação Fase 4 |
| Custo completo em minutos | indisponível | indisponível | indisponível | indisponível | indisponível | 0 tarefas | não há duração, adoção ou manutenção comparável |
| Falhas e abandono | indisponível | indisponível | indisponível | indisponível | não aplicável | 0 tarefas | formato anterior não permite atribuição confirmatória |
| Runner, retentativas e revisão | indisponível | indisponível | indisponível | indisponível | não aplicável | 0 tarefas | não há tarefa elegível no novo contrato |

O hash da entrada foi `4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945`.
A análise usou 2.000 reamostragens com semente `20260908`. Esses valores
identificam uma análise vazia, não uma medição de eficiência.

## F. Qualidade e custo completo

O método preserva falhas, abandono, pendências, retentativas, correções de
revisão, adoção e manutenção quando forem registrados. Nenhum desses campos
foi observado para uma tarefa elegível. Portanto, não há afirmação de ausência
de defeitos, regressões, incidentes ou custo transferido.

Os testes focais exercitam violação de segurança, defeito escapado e campo de
custo ausente. Eles validam o bloqueio do método, não a qualidade operacional
dos pilotos.

## G. Decisão por piloto

| Piloto | Conclusão | Evidência | Expandir? | Condições |
|---|---|---|---|---|
| Fase 1 | não avaliável | 0 tarefas válidas no analisador | não liberado | coletar antes e depois com o percurso realmente usado |
| Fase 2 | não avaliável | 0 tarefas válidas no analisador | não liberado | observar dado no consumidor e incluir builds, reinícios e falhas |
| Fase 3 | não avaliável | 0 tarefas válidas no analisador | não liberado | incluir adoções das duas consumidoras, jornada e recuperação |

Esta não é uma conclusão de ausência de ganho. É a decisão de não expandir
enquanto a comparação não existe.

## H. Expansão

Nenhum consumidor novo foi alterado. Não houve mudança de versão, novo PR de
adoção, publicação nova, jornada de expansão ou rollback. A expansão fica
suspensa até o protocolo liberar o piloto correspondente e um auditor
independente conferir a decisão.

## I. Clientes gerados

Avaliação não liberada. A condição de entrada, benefício demonstrado da Fase
3 e auditoria independente, não foi atendida. Nenhum contrato foi gerado,
migrado ou adotado por esta entrega.

## J. Auditoria

A autoauditoria conferiu a identidade, a deduplicação, os dados ausentes, as
fórmulas, o denominador zero, o intervalo pareado, a regressão de qualidade e
a reprodução do mesmo conjunto. A execução independente ainda não ocorreu.

O auditor deverá conferir a revisão `fase4-2026-09-08-1`, o hash da entrada,
as exclusões e a correspondência entre eventos e fontes. Sem isso, F4-11 não
é atendido e a fase não pode ser declarada concluída.

## K. Operação

```text
python ci/registrar_tarefa_fase4.py --manifesto <arquivo-json-da-tarefa>
python ci/analise_fase4.py --local
python -m pytest ci/tests/test_analise_fase4.py ci/tests/test_metricas_percurso.py -q
```

Resultado executado nesta bancada:

```text
50 passed in 0.49s
instrumentacao: parcial
avaliacao: em coleta
tarefas_validas: 0
eventos_historicos_ou_de_outras_fases: 2183
```

A suíte completa `python -m pytest ci/tests -q` terminou com 2.234 testes
aprovados, 11 pulados e 162 falhas em 462,75 segundos. As falhas ficaram nos
testes que executam shell, todos com `C:\WINDOWS\system32\bash.EXE` incapaz de
iniciar `/bin/bash` no WSL. A seleção diretamente relacionada à medição e às
muralhas passou com 118 testes em 6,28 segundos. O vermelho ambiental não foi
reclassificado como aprovação da suíte completa.

Uma segunda execução, após a guarda da escrita de `registrar_tarefa`, passou
com 120 testes em 7,50 segundos. Uma leitura posterior encontrou 2.186 eventos
históricos, ainda com zero tarefas válidas da Fase 4 e o mesmo hash de entrada.
Isso confirma a ausência de amostra, não cria uma medição nova.

A terceira execução, após as guardas de comparabilidade e consolidação de
tentativas, passou com 124 testes em 5,67 segundos. A leitura mais recente
encontrou 2.216 eventos históricos, que o agregador existente resume em 20
tarefas e 43 tentativas, ainda com zero tarefas válidas no contrato da Fase 4.

A execução final, após a cobertura explícita de contexto, passou com os mesmos
124 testes em 5,90 segundos. O resultado do analisador permaneceu inalterado.

Após a criação do comando operacional, a seleção completa passou com 129 testes
em 12,81 segundos. O comando válido escreveu no caderno privado durante os
testes e os manifestos incompletos foram recusados sem escrita.

Na leitura final, a fonte histórica tinha 2.222 eventos, 21 tarefas e 45
tentativas. A amostra confirmatória continuou com zero tarefas e zero tentativas
válidas, mantendo o mesmo hash de entrada.

A retomada é chamar `telemetria.registrar_tarefa` para uma tarefa legítima,
com a revisão, fonte, condição, classificação, estado, relógios e métricas
realmente observados. A análise é reproduzida pelo mesmo comando. A consulta
de evidências anteriores usa `gh pr view <numero> --json state,mergeCommit,url`
e `gh run view <id> --json status,conclusion,headSha,url`.

## L. Pendências

1. Coletar tarefas consecutivas elegíveis dos três pilotos, sem fabricar pares.
2. Usar o comando operacional no fechamento de tarefas reais, com manifesto
   preenchido pela fonte autorizada, sem criar valores ausentes.
3. Obter auditor independente com contexto e execução separados.
4. Recalcular a análise depois da coleta e antes de qualquer expansão.

## Conclusão global

**PARCIAL.** A Fase 4 tem instrumentação e protocolo executáveis, mas faltam
dados comparáveis, auditoria independente, decisão empírica e verificação de
expansão. Não há ganho comprovado e nenhum consumidor foi ampliado.
