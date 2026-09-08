# Auditoria independente da medição da Fase 4

Data da auditoria: 2026-09-08
Tarefa: TAR-281
Auditor: sessão `sessao-fabrica-auditoria-f4`
Implementador da coleta: sessão `sessao-ci-retomar-fase4-coleta-real`

## Veredito

**A auditoria é válida e a expansão continua bloqueada.** A análise da Fase 4
foi reproduzida com contexto e execução separados do implementador. O resultado
continua inconclusivo, sem benefício demonstrado e sem regressão demonstrada.

A evidência disponível comprova uma tarefa real na condição depois da Fase 1.
Ela não comprova linha de base, pareamento, qualidade operacional completa,
custo completo, recuperação ou publicação.

## Material conferido

| Item | Resultado |
|---|---|
| Protocolo | `docs/decisoes/PROTOCOLO-FASE4-MEDICAO.md`, congelado no commit `900c7481265b65d39db3b62ba396e4c4f4f0763f` antes da análise |
| Analisador | `ci/analise_fase4.py`, revisão `fase4-2026-09-08-1` |
| Revisão do instrumento | `bbe1036d0f8fb5b3e434fe36bc57ab7eee2f810e` |
| Entrada válida | SHA-256 `44cef42c07ac6c5e8325cab0e512a71aa8bd56e722f9df9b9dc4619d8bf9025c` |
| Fonte | `.git/telemetria-dos-robos/*.jsonl`, privada e fora do Git |
| Arquivos lidos | 209 |
| Arquivos ilegíveis | 0 |
| Linhas inválidas | 0 |

O caderno total mudou enquanto os comandos de auditoria registravam as próprias
fases, mas a entrada válida permaneceu com o mesmo hash. Por isso este parecer
usa o hash dos eventos `tarefa_medida`, e não a contagem histórica bruta como
identidade da amostra.

## Eventos brutos autorizados

Foram encontrados dois registros válidos, ambos da TAR-280 e da mesma tentativa
`sessao-ci-retomar-fase4-coleta-real`, com a mesma classificação e revisão do
instrumento:

| Observação | Estado | Início | Fim | Métricas |
|---|---|---|---|---|
| abertura | pendente | `2026-09-08T20:14:49.052742+00:00` | ausente | todas ausentes |
| fechamento | concluída | `2026-09-08T20:14:49.052742+00:00` | `2026-09-08T20:15:34.425556+00:00` | todas ausentes |

A consolidação preserva a retomada, soma uma tarefa e não cria uma tarefa nova.
O tempo observado da tarefa é 0,7562135667 minuto. Não há tempo de adoção,
manutenção, chamadas, runner, falhas escapadas ou violações de segurança
observados, portanto esses campos permanecem indisponíveis, não zero.

## Recálculo independente

O recálculo fora do analisador confirmou:

| Medida | Resultado |
|---|---:|
| Registros `tarefa_medida` | 2 |
| Tarefas consolidadas | 1 |
| Condição antes | 0 |
| Condição depois | 1 |
| Pares válidos | 0 |
| Registros sintéticos excluídos | 0 |
| Registros reais incompletos | 1 |
| Erros de leitura, correlação ou validação | 0 |
| Revisões do instrumento | 1 |

O hash independente da entrada válida foi o mesmo hash publicado pelo
analisador. A conclusão `inconclusivo` corresponde aos critérios do protocolo:
faltam 20 tarefas em cada condição, 10 pares completos, qualidade observada e
custo completo.

## Achados

### F4-AUD-01, médio, amostra insuficiente

**Evidência:** Fase 1 com antes 0, depois 1 e pares 0; Fases 2 e 3 sem
observações. **Impacto:** nenhuma comparação de benefício pode ser feita.
**Correção exigida:** continuar registrando tarefas reais elegíveis até haver
20 observações em cada condição e pelo menos 10 pares válidos. **Reteste:**
executar novamente `python ci/analise_fase4.py --local` e conferir a matriz de
amostra antes de qualquer expansão.

### F4-AUD-02, médio, qualidade e custo incompletos

**Evidência:** as métricas de custo, adoção, manutenção, defeitos escapados e
violações de segurança estão ausentes na única tarefa concluída. **Impacto:**
qualidade e custo completo não podem ser avaliados. **Correção exigida:**
preencher esses campos somente quando forem observados no fluxo real, sem
converter ausência em zero. **Reteste:** reproduzir a análise e verificar que
as coberturas passam a refletir observações reais.

### F4-AUD-03, médio, percurso sem prova de publicação

**Evidência:** o histórico do percurso tem 57 tarefas, 118 tentativas e 371
eventos correlacionados, mas zero publicações verificadas e as fases revisão,
integração e publicação ausentes. **Impacto:** o relógio e o resultado exigido
não cobrem o percurso completo. **Correção exigida:** registrar essas fases e
verificar o consumidor ou a borda pública quando a tarefa realmente publicar.
**Reteste:** executar a consolidação do percurso e conferir a cobertura de
publicação.

### F4-AUD-04, baixo, contagem bruta do caderno é móvel

**Evidência:** entre execuções, a contagem total de eventos aumentou porque os
próprios comandos de auditoria registraram fases, enquanto o hash dos eventos
válidos permaneceu `44cef42c07ac6c5e8325cab0e512a71aa8bd56e722f9df9b9dc4619d8bf9025c`.
**Impacto:** comparar somente `registros_encontrados` pode parecer uma mudança
na amostra. **Correção aplicada:** este parecer fixa o hash, a revisão e os
eventos autorizados. **Reteste:** repetir a análise e exigir o mesmo hash
enquanto nenhum novo `tarefa_medida` real entrar.

### F4-AUD-05, verde, exclusão sintética protegida

**Evidência:** o teste `test_sintetico_e_excluido_e_fica_explicado_no_diagnostico`
passou e a análise real reportou zero registros sintéticos. **Conclusão:** o
cenário controlado da TAR-282 não contaminou a amostra operacional.

### F4-AUD-06, verde, retomada não duplica tarefa

**Evidência:** dois registros da TAR-280 foram consolidados em uma tarefa e a
suíte passou nos testes de repetição, retomada, ausência e deduplicação.
**Conclusão:** a conclusão e a evidência correspondem ao mesmo trabalho real.

## Retestes executados

```text
python -m pytest ci/tests/test_analise_fase4.py ci/tests/test_registrar_tarefa_fase4.py ci/tests/test_metricas_percurso.py -q
63 passed in 0.64s

python ci/analise_fase4.py --local
instrumentacao: implementada
avaliacao: inconclusiva
registros_tarefa_medida: 2
tarefas_validas: 1
fase1 antes=0 depois=1 pares=0 custo_completo_depois=indisponivel
fase2 antes=0 depois=0 pares=0
fase3 antes=0 depois=0 pares=0
entrada_sha256: 44cef42c07ac6c5e8325cab0e512a71aa8bd56e722f9df9b9dc4619d8bf9025c
```

## Decisão operacional

TAR-281 pode ser concluída como auditoria independente da entrada atual. Ela
não libera expansão, não cria amostra artificial e não transforma ausência em
zero. A próxima pendência técnica é coletar observações reais comparáveis,
com qualidade, recuperação, custo completo e publicação verificáveis.
