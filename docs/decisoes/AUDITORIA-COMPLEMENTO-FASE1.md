---
publico-para-ia: true
---

# Auditoria do complemento da Fase 1

## Veredito deste retrato

**PARCIAL.** F1-01 e F1-02 foram atendidos no alcance da instalação inspecionada. F1-03 e F1-04 têm código aprovado, duas validações amplas reais e retomada conferida de forma independente. F1-03 foi integrado e seu deploy concluiu com sucesso. Os três achados de código foram corrigidos e retestados. F1-05 ainda depende da revisão deste documento e da última validação da revisão que o embarca; F1-06 depende das integrações e verificações de publicação restantes. A Fase 1 não está concluída. Ganho de eficiência não comprovado.

Este é um retrato da revisão em 08/09/2026, depois das provas e dos snapshots de 05:08:19 UTC, preparado sobre ef1d5d3b3fd267e0afe6333cd103b33dc0996c9a. Não é uma fonte nova de estado operacional. Os [PRs 1382](https://github.com/abundanciabr/sitesdoreino/pull/1382) e [1383](https://github.com/abundanciabr/sitesdoreino/pull/1383), seus runs e o livro de ocorrências registram os estados posteriores. O arquivo não afirma ter verificado o próprio deploy. A prova pública posterior será registrada no corpo do PR e no livro, evitando uma sequência de documentos que precisam comprovar a própria publicação.

A missão corretiva atual e as emendas das Leis 2 e 4 da CONSTITUICAO são a autoridade deste trabalho, com mandato expresso para ci/. Documentos históricos foram preservados como história, sem se tornarem receitas ativas.

## Revisões e alcance

| Parte | Revisão | Prova e limite |
|---|---|---|
| Base anterior ao complemento | 87365d3234fdb2ea3543986d80ba196ba36f36f3 | Não recebe aprovação retroativa das correções |
| Contexto e receitas, código | d24e0aac0af7c661ccb14026642690ec40a8049d | 15 arquivos de código e receitas |
| Contexto com recibo | fbc4520cea95e1316a2143b52ebf22d13effa1ae | [PR 1381](https://github.com/abundanciabr/sitesdoreino/pull/1381), recibo de 977 bytes, validação isolada repetida |
| Contexto integrado | ffedbd7c083f893e7e3e3201f32a6acc0ae75b9c | PR 1381 MERGED; [deploy 34187392935](https://github.com/abundanciabr/sitesdoreino/actions/runs/34187392935) completed/success; CLI integrado executado |
| Prazo, revisão rejeitada | 041ddea25e6bc938a2025699f89eecb377ee4a25 | Suíte ampla passou, mas filho Linux com setsid sobreviveu ao timeout no ensaio independente; fechamento recusou árvore alterada antes do push |
| Prazo corrigido, runtime aprovado | 0d69aaf5723d5d3ede5f85ccb7e5cf60a9ca8302 | Commit 04:43:11 UTC; achado ALTO encerrado pelo revisor após reprodução real Windows/Linux |
| Cobertura individual, código e recibo iniciais | edf0a808f295c02d69a009597a24d0a5b55097e5 e 1b35c92f11cadbaada291c96db9d2447d3bf1481 | Três validações isoladas com exit 0 em cada SHA; PR 1382 aberto |
| Composição do piloto de abertura e execução | f78baea846829c7bfded19551c22fb8d7a54364e | Contexto integrado à bancada; abertura real e 97 testes; não é merge de PR 1382 na main |
| Composição da primeira ampla | 0a804da6c86a48eacda5367181a4e3d65311eb0f | 2382 passaram e 5 foram pulados; 454.44s; revisão holística independente |
| Composição com recibo, segunda ampla e retomadas | 4b256066f5f9d365b551558b4330eacfb932b029 | 2382 passaram e 5 foram pulados; 376.90s; duas retomadas com provas novas no mesmo SHA |
| Prazo com organização final dos testes | a38efecbe05c73ca60a75c1c07023f70b7eb1095 | PR 1383 revisado; 55 corpos de testes idênticos por AST, armadilha 401 e recibos 032/034; runtime idêntico a 0d69aaf5 |
| Composição local depois dessa organização | ef1d5d3b3fd267e0afe6333cd103b33dc0996c9a | As duas amplas são dos SHAs acima. A composição posterior não muda o runtime testado; o último fechamento focal e a revisão do documento permanecem separados |

A catraca de CI apontou falso positivo na organização dos testes de processos. A correção moveu os corpos existentes para dois arquivos específicos; a comparação AST de 55 corpos foi revisada independentemente. Nenhum controle foi removido. A pista atualizou o ramo do PR 1383 após a revisão a38efecb: a diferença informada pela maestro contém exatamente os 16 arquivos do PR 1381 já presentes na composição testada. Os sete checks ficaram verdes novamente e a pista integrou o PR 1383 em 075d3b469e5b5f08bfd6aa824e70c5aad404a6be. A maestro confirmou MERGED por gh pr view e o [deploy 34189715598](https://github.com/abundanciabr/sitesdoreino/actions/runs/34189715598) por gh run view: status completed, conclusion success e headSha 075d3b469e5b5f08bfd6aa824e70c5aad404a6be. Os registros 035 e 036 distinguem integração e deploy. O PR 1382 permanece aberto.

As alterações posteriores às amplas foram a organização de testes com corpos preservados, a lição 401, recibos e este retrato documental. Não se atribuem aos SHAs das amplas os bytes de um documento escrito depois. A validação final da revisão que o embarcará é responsabilidade do fechamento seguinte.

A atualização da bancada com origin/main após o merge 075d3b46 não mudou o conteúdo de runtime testado. O clone principal foi atualizado por fast-forward até 075d3b46, e a maestro conferiu novamente os três SHA256 das instruções locais, todos preservados. Esse deploy não comprova a publicação da versão final deste documento.

## Matriz F1-01 a F1-06

| ID | Critério e resultado observado | Estado da revisão |
|---|---|---|
| F1-01 | Índice integral deixou de ser obrigatório nas fontes ativas rastreadas. Contexto mantém leis globais, de célula e dos caminhos, origem, ausência e truncamento; índice continua aprofundamento. Vermelho, 245 testes verdes, 17 mutações e pilotos reais | ATENDIDO no alcance inspecionado; PR 1381 integrado e deploy conferido |
| F1-02 | Receitas de abertura e fechamento usam os instrumentos existentes; escrivão não é obrigatório para repetir reserva e recibo. Três instruções locais foram alinhadas, com hashes e backups privados; CLI integrado foi executado | ATENDIDO no alcance de capacidade e instalação inspecionada; não houve novo agente TOML nem verificação de hot reload ou hooks |
| F1-03 | JSON existente aceita prazo_segundos inteiro de 1 a 7200, padrão 900 por comando. Timeout é distinto de falha e encerra descendentes Windows/Linux; correção de setsid foi reproduzida e aprovada independentemente | ATENDIDO na revisão; amplas compostas concluídas; PR 1383 integrado em 075d3b46 e deploy 34189715598 completed/success |
| F1-04 | Cobertura é individual por tarefa, tentativa, ramo e revisão. Observações preservam transições; ausência não vira dispensa. Piloto e retomada mantiveram 14 fatos, um PR, reservas e bytes dos dois recibos prévios, com provas novas | CÓDIGO E PILOTO APROVADOS pelo revisor; integração do PR 1382 pendente |
| F1-05 | Pacote sanitizado contém matriz, quinze respostas reais atribuídas ao revisor, SHAs, comandos, resultados, trechos de logs e hashes | Documento atualizado; última validação e revisão de seu diff pendentes |
| F1-06 | Integração, deploy e comportamento publicado são estados separados. Cinco entregas históricas, seus deploys e bytes de um mapa público foram conferidos; PRs 1381 e 1383 integrados, com deploys conferidos | Integração de PR 1382 e publicação aplicável pendentes; não há conclusão global |

## As quinze respostas do revisor independente

Parecer de **/root/auditoria, papel revisor**, em recurso de colaboração separado do implementador. A revisão holística examinou 0a804da6 sobre a base 87365d32 e executou 187 testes com 5 skips em 39.19s. A atualização posterior leu os seis logs das amplas, conferiu os hashes e aprovou a retomada em 4b256066, recalculando eventos brutos, saída do CLI e snapshots. As respostas abaixo são a síntese atribuída desse parecer real, transmitido pela maestro, com os limites mantidos.

1. **O percurso foi automatizado ou apenas mudou etapas manuais de lugar?** Abertura e fechamento executam efeitos pelos instrumentos existentes. O piloto de execução foi medido por chamada explícita à API registrar_fase; isso não prova um hook automático.

2. **Alguma ferramenta ou função existente foi duplicada?** Não foi criado orquestrador, fila ou executor externo. A contenção de processos Windows/Linux pertence ao runner de fechamento existente.

3. **As contradições foram resolvidas por autoridade rastreável?** A missão corretiva e as emendas das Leis 2 e 4 orientaram as alterações, com mandato expresso para ci/.

4. **Alguma instrução ativa ainda exige o procedimento antigo?** As fontes ativas rastreadas e as três cópias locais inspecionadas foram alinhadas. A história foi preservada como história, sem impor a receita antiga. A conclusão não certifica outras instalações.

5. **O contexto direcionado pode omitir regras obrigatórias?** Leis globais, de célula e AGENTS ancestrais continuam obrigatórios. Ausência e truncamento têm aviso. A presença dessas referências não prova a leitura efetiva pelo agente.

6. **A telemetria distingue mensagens, ferramentas, tarefas e tentativas?** Uso de mensagens e ferramentas permanece separado; fases são correlacionadas por tarefa, tentativa, ramo e commit. Presença global não equivale a completude individual.

7. **A deduplicação ou agregação pode produzir contagens incorretas?** Uma duplicação exata não conta como fato novo; observações preservam transições. Os dois achados de repetição temporal de F1-04 foram corrigidos e retestados. A retomada real confirmou a distinção entre fatos e observações.

8. **O fechamento aceita prova ausente, antiga ou de outra revisão?** Validação ocorre em commit isolado e se repete após o recibo. Prova antiga ou ausente não libera o fechamento. Prazo, timeout e estado de erro de instrumento são tratados separadamente.

9. **A retomada pode duplicar efeitos?** O comando consulta PR, reserva, recibo e eventos e exige provas novas. A retomada em 4b256066 foi aprovada independentemente: fatos, reservas e recibos permaneceram estáveis; duas provas foram acrescentadas. Os dois recibos já existiam para revisões diferentes. TAR-278 coordena a missão e não foi encerrada artificialmente pelo piloto.

10. **Existe caminho que contorne revisão ou permissões?** Não foi observado bypass de revisão, merge ou autenticação. A pista continua responsável pela integração.

11. **As mudanças invadiram as fases 2 ou 3?** O diff não invade a arquitetura prevista para essas fases. As correções permanecem no complemento da Fase 1.

12. **Algum teste ou controle foi enfraquecido?** Os controles foram preservados; o prazo configurável é finito. Houve crescimento de cobertura e sabotagens detectadas. A organização posterior conservou 55 corpos de testes por comparação AST, sem afrouxar a catraca.

13. **Logs e recibos expõem informações sensíveis?** O revisor leu fontes, saídas e recibos e retestou a sanitização; não viu segredo nem transcrição. O pacote publica recortes, hashes e comandos sanitizados. Logs privados e backups globais não são publicados integralmente.

14. **As alegações de eficiência têm medição válida?** Não há alegação de ganho comprovado. Tempo local de teste e bytes de contexto não foram convertidos em tokens, economia de consumo ou ganho global.

15. **Um agente novo consegue executar o fluxo pela documentação atual?** Receitas e CLI executáveis são coerentes com os arquivos inspecionados. Não foi instanciado novo agente a partir do TOML nem verificado hot reload. A tentativa de criar um agente novo foi recusada pelo limite de threads; nenhum agente nasceu. O revisor interpretou o aceite como capacidade do fluxo, sem uma ordem explícita de instanciar novo agente.

O revisor encerrou os achados de F1-03 e F1-04. Seu estado global continua PARCIAL por evidência documental final e publicação pendentes, não por achado de código aberto. Não aplicável exige declaração e justificativa; ausência de evento permanece ausência de evidência.

## Provas focais, baseline e mutações

Ambiente principal: Windows 11, Python 3.12.10. As provas Linux usaram Docker com montagem somente leitura, rede desabilitada e a imagem já disponível identificada abaixo. Os cinco skips Windows são casos explicitamente Linux de adoção de órfãos, cobertos no ensaio Linux correspondente. Uma seleção -k não transforma casos excluídos em aprovados.

O [corpo público do PR 1381](https://github.com/abundanciabr/sitesdoreino/pull/1381) contém os comandos, horários UTC, saídas e 17 mutações de contexto, relidos após publicação. As provas seguintes registram o comportamento observado, não somente nomes de testes.

| Ensaio | Revisão e comando | Saída real |
|---|---|---|
| Baseline de contexto | Base 87365d32, pytest em test_sessao, test_sessao_contexto, test_sessao_retomada, test_fichas_de_robo e test_indice_de_armadilhas | 182 passed in 13.90s |
| Guardas novos antes da correção | python -m pytest ci/tests/test_sessao_contexto.py ci/tests/test_fichas_de_robo.py -q | 5 failed, 31 passed in 3.95s |
| Contexto corrigido isolado | fbc4520c, suíte ampliada abaixo | 245 passed in 23.39s |
| Prazo antes da correção | Guardas novos contra a versão anterior | 24 failed, 60 deselected in 0.79s |
| Baseline amplo anterior às correções | python -m pytest ci/tests -q -n 4 | 2334 passed in 457.98s; não aprova a versão corrigida |
| Ampla intermediária reprovada depois | 041ddea2, mesmo comando pelo runner com prazo 1800; 04:28:36.504439 a 04:34:50.435382 UTC | 2362 passed in 373.23s; achado setsid posterior impede aprovar essa revisão |
| Prazo corrigido, implementador Windows | 0d69aaf5, python -m pytest ci/tests/test_pr.py -q | 90 passed, 5 skipped in 16.35s |
| Prazo corrigido, implementador Linux | 0d69aaf5, comando Docker final abaixo | 34 passed, 61 deselected in 12.19s |
| Prazo corrigido, revisor Windows | Mesmo runtime, pytest focal | 90 passed, 5 skipped in 25.92s |
| Prazo corrigido, revisor Linux | Docker --init; reprodução de setsid e seleção focal | 34 passed, 61 deselected in 17.48s; TIMEOUT, filho morto e recolhido, sem /proc/PID |
| Métricas, baseline e correção | python -m pytest ci/tests/test_metricas_percurso.py ci/tests/test_metricas_da_fabrica.py -q | Baseline 48 passed in 9.16s; correção 61 passed in 2.02s e 2.33s |
| Métricas, revisor separado | Mesmo comando e guardas adicionais | 60 passed in 2.03s e 61 passed in 2.27s |
| Piloto composto | f78baea8, métricas, contexto e fichas | 97 passed in 3.85s; processo completo 4.625s |
| Revisão holística independente | 0a804da6, métricas, prazo, contexto e fichas | 187 passed, 5 skipped in 39.19s |

Suíte ampliada de contexto executada, além da geração do índice e da verificação de travessão:

```text
python -m pytest ci/tests/test_sessao.py ci/tests/test_sessao_contexto.py ci/tests/test_sessao_retomada.py ci/tests/test_fichas_de_robo.py ci/tests/test_indice_de_armadilhas.py ci/tests/test_indice_com_a_origem.py ci/tests/test_padrao_de_trabalho.py ci/tests/test_licao_do_caminho.py -q
python ci/indice_de_armadilhas.py
python ci/travessao.py
```

Índice: PASS, 375 entradas. Travessão: PASS, 167 arquivos inspecionados e dívida herdada estável. O primeiro texto adicional de CLAUDE excedeu o teto, chegando a 20.221 caracteres; foi condensado para respeitar o teto, preservando o controle.

Comando Linux final executado, com somente o caminho pessoal substituído por BANCADA:

```text
docker run --rm --init --network none --mount "type=bind,source=BANCADA,target=/repo,readonly" --workdir /repo --entrypoint python ghcr.io/abundanciabr/plataforma-checkout:14be60c6359b9c7c9a37242822c36bf319c01cba -m pytest ci/tests/test_pr.py -q -k "prazo or timeout or instrumento or linux" -p no:cacheprovider
```

--init impede que pytest seja PID 1 e mascare a adoção de órfãos. O ensaio inicial de 27 testes em 8.52s e os 88 testes Windows em 11.34s pertencem à correção anterior ao achado setsid. Não são reapresentados como aprovação do runtime final. O baseline amplo não tinha horário embutido no log; seu horário reconstruído não é tratado como medição exata.

## Três achados independentes corrigidos

| Achado | Reprodução real | Correção e reteste | Estado |
|---|---|---|---|
| F1-04: reabertura parecia concluída | Fechamento iniciado às 00:01, concluído às 00:02 e reiniciado às 00:03 retornava concluído | consolidar_percurso preserva últimas observações; guarda test_reinicio_de_fechamento_na_mesma_identidade_nao_fica_concluido, mutação e reteste independente | ENCERRADO |
| F1-04: nova aprovação permanecia falha | Validação concluída às 00:00, falhou às 00:01 e concluída às 00:02 retornava falha | observado_em preserva transições; guarda test_revalidacao_observada_apos_falha_preserva_transicoes e reteste independente | ENCERRADO |
| F1-03, ALTO: filho Linux com setsid escapava do timeout | Revisor confirmou processo vivo fora do grupo original em 041ddea2 | ci/pr_processos_linux.py usa subreaper para adotar, encerrar e recolher gerações, restaura estado e recusa preexistência, concorrência e /proc indisponível; revisor reproduziu TIMEOUT em 0d69aaf5 sem filho sobrevivente | ENCERRADO em 0d69aaf5 |

Recortes reais preservam o que falhou:

```text
Contexto antes da correção:
AssertionError: assert 'INDICE.md' not in 'Leituras obrigatórias: ...'
5 failed, 31 passed in 3.95s

Mutação de repetição temporal:
assert not r["por_tentativa"][0]["percurso_local_concluido"]
E assert not True
2 failed, 42 deselected in 0.13s

Mutação de publicação importada:
assert local["fases"]["publicacao"]["estado"] == "sem_evidencia"
E AssertionError: assert 'verificado' == 'sem_evidencia'
1 failed, 43 deselected in 0.13s

Defeito real Linux antes da correção final:
FAILED ci/tests/test_pr.py::test_timeout_encerra_filhos_e_netos_reais[True-False]
FAILED ci/tests/test_pr.py::test_timeout_encerra_filhos_e_netos_reais[True-True]
2 failed, 2 passed, 86 deselected in 32.42s
```

O primeiro recorte é abreviado, não um log integral. As sabotagens abaixo foram restauradas; o achado setsid foi defeito real, distinto das mutações deliberadas.

| Grupo de mutação | Resultado real |
|---|---|
| Cobertura: tarefas-fundidas | exit 1; 1 failed, 43 deselected in 0.17s |
| Cobertura: tentativas-fundidas | exit 1; 1 failed, 1 passed, 42 deselected in 0.13s |
| Cobertura: primeira-observacao | exit 1; 2 failed, 42 deselected in 0.13s |
| Cobertura: falha-como-sucesso | exit 1; 3 failed, 41 deselected in 0.14s |
| Cobertura: fechamento-sem-pr | exit 1; 1 failed, 43 deselected in 0.12s |
| Cobertura: publicacao-importada | exit 1; 1 failed, 43 deselected in 0.13s |
| Prazo: entrada | exit 1; 15 failed, 73 deselected in 0.61s |
| Prazo: configuracao | exit 1; 3 failed, 1 passed, 84 deselected in 0.30s |
| Prazo: timeout | exit 1; 2 failed, 86 deselected in 4.37s |
| Prazo: job_windows | exit 1; 2 failed, 86 deselected in 15.97s |
| Prazo: suspensao_windows | exit 1; 1 failed, 87 deselected in 0.32s |
| Prazo: retomada | exit 1; 2 failed, 86 deselected in 0.31s |
| Prazo: grupo de processos POSIX | exit 1; 2 failed, 86 deselected in 27.53s |
| Contexto e receitas | 17 de 17 mutações detectadas com exit 1; detalhes no PR 1381 |

Mutações adicionais Linux da correção 0d69aaf5:

| Guarda sabotado | Resultado real |
|---|---|
| adocao | exit 1; 4 failed, 91 deselected in 52.60s |
| encerramento | exit 1; 4 failed, 91 deselected in 11.42s |
| restauracao | exit 1; 1 failed, 1 passed, 93 deselected in 3.51s |
| preexistente | exit 1; 1 failed, 94 deselected in 3.45s |
| concorrencia | exit 1; 2 failed, 93 deselected in 4.38s |
| proc | exit 1; 1 failed, 94 deselected in 2.93s |

## Duas validações amplas reais pelo runner

A configuração existente de validação escolheu prazo_segundos: 1800 e três comandos. ci/pr.py executou cada revisão em worktree isolado, repetindo a validação após embarcar o recibo:

```json
{"prazo_segundos":1800,"comandos":[["python","-m","pytest","ci/tests","-q","-n","4"],["node","painel/gerar_manifesto.js"],["node","painel/gerar_manifesto.js","--conferir"]]}
```

Os seis logs foram lidos integralmente na preparação deste retrato e pelo revisor. Seus hashes foram conferidos com os arquivos originais. A tabela e os recortes publicados omitem caminhos pessoais e linhas repetidas de progresso; os SHA256 identificam os logs originais completos. Datas abaixo são UTC em 08/09/2026.

| Revisão e comando | Início UTC | Fim UTC | Resultado real | SHA256 do log integral |
|---|---|---|---|---|
| 0a804da6, pytest amplo | 2026-09-08T04:48:48.445381+00:00 | 2026-09-08T04:56:23.785558+00:00 | 2382 passed, 5 skipped in 454.44s (0:07:34); exit 0 | be9cd7609be7fe13ca9044b55dd29a4e3910d2d44a0820c0572151a6b728de61 |
| 0a804da6, node gerar_manifesto.js | 2026-09-08T04:56:23.785558+00:00 | 2026-09-08T04:56:24.953196+00:00 | PASS, exit 0; 1089 registros válidos, 2 meses; exit 0 | adf8531834464c96f77580eb3474e3809fe00a251380ad7c1f5bed11b08c2895 |
| 0a804da6, node gerar_manifesto.js --conferir | 2026-09-08T04:56:24.953196+00:00 | 2026-09-08T04:56:25.897890+00:00 | PASS, exit 0; 1089 registros válidos, 2 meses; exit 0 | 3a6eca22450e2f0b1e3b71c929d5a6bd636686374b802988aae65b16ded9d1dd |
| 4b256066, pytest amplo | 2026-09-08T04:56:38.823774+00:00 | 2026-09-08T05:02:56.407189+00:00 | 2382 passed, 5 skipped in 376.90s (0:06:16); exit 0 | df57565c89bde126ad41b40009729f05c8b9baff27b17d88a5f4e659e6518930 |
| 4b256066, node gerar_manifesto.js | 2026-09-08T05:02:56.408191+00:00 | 2026-09-08T05:02:57.367741+00:00 | PASS, exit 0; 1090 registros válidos, 2 meses; exit 0 | 602b3eb2f0e8bbdd400ae93072ddfd1970434a0f2a40a3c224b473c34f53df44 |
| 4b256066, node gerar_manifesto.js --conferir | 2026-09-08T05:02:57.367741+00:00 | 2026-09-08T05:02:58.291877+00:00 | PASS, exit 0; 1090 registros válidos, 2 meses; exit 0 | b166ba41d7d74847ccd8862573e8abe796183ed3a647902dec0569ea987ae5b6 |

Recortes dos logs amplos, com STDERR vazio nas seis execuções:

```text
0a804da6:
Prazo por comando: 1800s
Resultado: PASS
Exit: 0
2382 passed, 5 skipped in 454.44s (0:07:34)

4b256066:
Prazo por comando: 1800s
Resultado: PASS
Exit: 0
2382 passed, 5 skipped in 376.90s (0:06:16)
```

O runner recusou confirmar imediatamente o SHA remoto após a segunda ampla. Consultas posteriores por gh pr view e git ls-remote confirmaram 4b256066. A retomada revalidou e concluiu; a recusa original não foi reclassificada retroativamente como sucesso.

## Piloto e retomada correlacionados

Abertura real em f78baea8, iniciada em 04:41:41.845486 UTC, exit 0 em 6.953s:

```text
python ci/sessao.py --celula ci --tarefa complemento-f1 --sem-container --frase "Concluir e comprovar a cobertura individual da primeira fase" --caminho ci/metricas_da_fabrica.py --caminho ci/pr.py --aceite "Abertura, contexto, execução, validação, fechamento e retomada correlacionados sem duplicação"
```

Execução real em f78baea8, iniciada em 04:42:48.540331 UTC, exit 0 em 4.625s:

```text
python -m pytest ci/tests/test_metricas_percurso.py ci/tests/test_metricas_da_fabrica.py ci/tests/test_sessao_contexto.py ci/tests/test_fichas_de_robo.py -q
97 passed in 3.85s
```

A execução foi envolvida explicitamente pela API existente registrar_fase; não foi observada automaticamente por hook. A tarefa e o ramo do piloto são agent/ci/complemento-f1, e a tentativa é 5199ca31faa045dfba4186644a239dd2. TAR-278 é a coordenação da missão: o piloto não passa TAR ao fechamento e não encerra artificialmente a tarefa. Eventos da fila são cobertos pelos testes controlados existentes, não por uma conclusão real inventada para a auditoria.

As duas retomadas usaram ci/pr.py --continuar com os arquivos de mensagem, corpo, detalhe e validação existentes e a lista explícita de arquivos de F1-04 e seus registros. Em cada retomada, o runner consultou o PR 1382 e executou duas passagens dos três comandos abaixo, todas em 4b256066:

```text
python -m pytest ci/tests/test_metricas_percurso.py ci/tests/test_metricas_da_fabrica.py ci/tests/test_pr.py ci/tests/test_sessao_contexto.py ci/tests/test_fichas_de_robo.py -q
node painel/gerar_manifesto.js
node painel/gerar_manifesto.js --conferir
```

| Retomada e passagem | Janela UTC dos três comandos | Resultado pytest | Geração e conferência |
|---|---|---|---|
| 1, primeira | 05:04:21.844073 a 05:04:41.382068 | 187 passed, 5 skipped in 16.73s | PASS, exit 0 em ambos |
| 1, segunda | 05:04:49.210266 a 05:05:09.452745 | 187 passed, 5 skipped in 17.47s | PASS, exit 0 em ambos |
| 2, primeira | 05:06:14.963787 a 05:06:34.575583 | 187 passed, 5 skipped in 16.67s | PASS, exit 0 em ambos |
| 2, segunda | 05:06:42.286947 a 05:07:01.755788 | 187 passed, 5 skipped in 16.70s | PASS, exit 0 em ambos |

Os seis logs da segunda retomada foram conferidos independentemente pelo revisor, incluindo os resultados 16.67s e 16.70s. As duas saídas finais do runner foram:

```text
PASS validação local concluída; recibo embarcado e revisão remota conferida
Revisão: não verificada. Integração: não verificada. Publicação: não verificada.
PR 1382 aberto com recibo: https://github.com/abundanciabr/sitesdoreino/pull/1382; devolva à maestro para revisão e espera.
```

Essa saída é a declaração do runner naquele instante; não substitui a revisão independente registrada posteriormente neste retrato. Os snapshots de 05:06:11.153197 e 05:08:19.760156 UTC foram comparados pelo script conferir_retomada.py e por reexecução somente leitura das comparações nesta preparação. O revisor recalculou também os dados brutos e o CLI. Resultado sanitizado:

```json
{
  "resultado": "PASS",
  "revisao": "4b256066f5f9d365b551558b4330eacfb932b029",
  "tentativa": "5199ca31faa045dfba4186644a239dd2",
  "pr": 1382,
  "prs": 1,
  "recibos": 2,
  "nota_recibos": "Dois fatos prévios de revisões diferentes, edf0a808 e 0a804da6; nenhum novo na retomada.",
  "eventos_logicos": 14,
  "observacoes_antes": 15,
  "observacoes_depois": 19,
  "novas_provas": 2,
  "reservas_inalteradas": true,
  "recibos_bytes_inalterados": true,
  "percurso_local_concluido": true,
  "tentativa_anterior_preservada_incompleta": true
}
```

A comparação usa tarefa, tentativa, branch, commit, PR, fase, resultado e contexto_bytes para definir cada fato. Houve 14 fatos antes e depois, 15 para 19 observações e 6 para 8 provas. A tentativa 5199ca31faa045dfba4186644a239dd2 ficou completa localmente, correlacionada a 4b256066 e PR 1382. A tentativa anterior 0dc74cc82b7e40a9afd2810a61789ff3 permaneceu incompleta; suas lacunas não foram preenchidas pelos eventos da outra tentativa.

Os dois recibos são fatos legítimos anteriores de revisões diferentes, edf0a808 e 0a804da6. Nenhum recibo foi criado pela repetição. Seus bytes e referências de reserva permaneceram iguais:

| Recibo | SHA256 dos bytes | Commit da referência de reserva |
|---|---|---|
| 20260908-031-ci-separa-a-cobertura-de-cada-tentativa.js | cc5960e94ee36002b42a7ace0a8297d4d1f92bc0b36ecf76d35c09b2a5e919e1 | 234270675fa0a503cb1dd49e68006d79279acf75 |
| 20260908-033-ci-separa-a-cobertura-de-cada-tentativa.js | 8eb7503ab35c50ab6902c3c9a33e8423b6d72a377c45be4aa0c2a17fbe091deb | d9cc903aac7897303056e6919de201b63d258136 |

No piloto anterior do PR 1381, bancada suja foi recusada com os arquivos preservados; após commit, a abertura concluiu. A retomada produziu um PR e um recibo de 977 bytes. Os contextos de múltiplos alvos, vazio, truncado e ampliado emitiram 5.623, 689, 2.291 e 3.837 bytes, respectivamente. São consultas diferentes, sem equivalência com ganho de eficiência. A ausência explícita e o truncamento foram observados, com lições 179/373 no caso de múltiplos alvos.

## Instruções locais e origem das regras


CLAUDE.md e .claude/agents são rastreados. A Constituição rege as leis; RITOS, RUNBOOK, PLAYBOOK, ARMADILHAS, CAMINHO-DOURADO e os moldes são receitas. ci/sessao.py recupera contexto; ci/indice_de_armadilhas.py gera arquivos ignorados, que continuam acessíveis para aprofundamento.

A instalação local foi inspecionada pela maestro. AGENTS.md recebeu ajustes nas três seções de contexto, bancada e lote; as fichas despacho/revisor em .codex/agents tiveram developer_instructions alinhado à fonte .claude. Os demais campos TOML foram preservados por comparação estruturada. Não foi identificado gerador canônico de toda a instalação Codex. O script aplicado preservou backups, diffs e hashes antes/depois; os backups permanecem privados, sem publicação do conteúdo global.

| Arquivo local | SHA256 antes | SHA256 depois |
|---|---|---|
| AGENTS.md | 61d74c8f4d9df44f2a0a7383a22c748c36d69642bf61c13f4ef3cdb60d70050e | bd09dff48810146e085a6abbceba6c9c5cf0860ea646c9d1aa9be87bc9872a87 |
| .codex/agents/despacho.toml | d825bbb764c39d0bd5572f8c79d1daa2ff79bdbc995157f035c9b12b1bbb265d | 6fcf4bf07ec0b6e8085d0bd6700e521033eb2726d39b5ebf990c4b28ddf5d9f8 |
| .codex/agents/revisor.toml | 2f382c75a9880f89e837fbd9450ed63ab49f163f4fe295764db059ea2c6366d1 | d2ba23f9838d2f910d818bafc0c427190a42b1997bf40b12814decc8666d6418 |

Os hashes foram relidos e comparados aos três arquivos locais. Após conferir árvore rastreada e índice limpos, a maestro atualizou o clone principal por fast-forward até ffedbd7c e verificou a preservação dessas três instruções locais. Um hash identifica os bytes; não substitui a inspeção que a maestro realizou. Estes ajustes não viajam no Git e não certificam outras instalações.


A prova integrada posterior foi executada de verdade no clone principal ffedbd7c, com exit 0:

```text
python ci/sessao.py --contexto --celula ci --tarefa contexto-integrado-f1 --sem-container --caminho ci/sessao.py --sintoma "leitura integral"
```

A saída exigiu CLAUDE.md, AGENTS.md, CONSTITUICAO.md, RITOS.md e Retrospectiva; declarou explicitamente não ter recuperado lições e apresentou o índice em Aprofundamento. Isso comprova CLI integrado e inclusão de AGENTS local. Arquivos locais e CLI foram inspecionados; não houve prova de hot reload, hooks ou instanciação de um novo agente com o TOML. A tentativa de nova instanciação foi recusada por limite de threads e não criou agente. Também não há prova de tela administrativa ou autenticação nessa execução.

## Entregas anteriores: integração e deploy conferidos


Consulta estruturada registrada em 08/09/2026 às 04:23:40 UTC por gh pr view e gh run view. MERGED e success abaixo pertencem aos PRs históricos; não são aprovação automática das correções atuais.

| PR | Commit integrado | Merge UTC | Deploy observado |
|---|---|---|---|
| [1376](https://github.com/abundanciabr/sitesdoreino/pull/1376) | 9b805aa618073fecc296447169c009cf1d953df8 | 2026-09-08T02:02:16Z | [completed/success](https://github.com/abundanciabr/sitesdoreino/actions/runs/34178664534), headSha igual ao commit integrado |
| [1377](https://github.com/abundanciabr/sitesdoreino/pull/1377) | 0ffa2431b1f315107cff338df2345fdace41169b | 2026-09-08T02:26:32Z | [completed/success](https://github.com/abundanciabr/sitesdoreino/actions/runs/34180062778), headSha igual ao commit integrado |
| [1378](https://github.com/abundanciabr/sitesdoreino/pull/1378) | 374a7c2eb0e5a34ffc6b0bdb9ec71d9332bc39f3 | 2026-09-08T02:07:55Z | [completed/success](https://github.com/abundanciabr/sitesdoreino/actions/runs/34178994205), headSha igual ao commit integrado |
| [1379](https://github.com/abundanciabr/sitesdoreino/pull/1379) | 1b33043acb4cc648bb26eed25a2a4f6f54207fd5 | 2026-09-08T02:29:17Z | [completed/success](https://github.com/abundanciabr/sitesdoreino/actions/runs/34180217120), headSha igual ao commit integrado |
| [1380](https://github.com/abundanciabr/sitesdoreino/pull/1380) | 87365d3234fdb2ea3543986d80ba196ba36f36f3 | 2026-09-08T02:48:59Z | [completed/success](https://github.com/abundanciabr/sitesdoreino/actions/runs/34181358930), headSha igual ao commit integrado |

A prova pública histórica foi somente do [mapa de leis e ritos](https://meshcraft.top/mapa-ia/01-leis-ritos-e-invariantes.md): HTTP 200, 15.742 bytes, iguais ao git show da revisão 87365d3234fdb2ea3543986d80ba196ba36f36f3; SHA256 1fea72228b9ebcaa2434e7fe65a1dd980a478e1bf3646c0d83f36de0fde28302. Isso não comprova o conteúdo de documentos privados nem de recibos na tela administrativa.

## Publicação aplicável e limites de acesso

Este conteúdo usa o canal existente [plano de auditoria para IA](https://meshcraft.top/mapa-ia/planos/AUDITORIA-COMPLEMENTO-FASE1.md). O link é o destino esperado; seu GET final ainda não foi verificado neste retrato. A marca publico-para-ia: true está nos primeiros 2048 caracteres. O deploy-celula já embute docs/decisoes na imagem de admin, e planos_para_ia.py serve os documentos autorizados. A rota, autenticação e fontes de estado existentes permanecem responsáveis pela entrega.

Em 08/09/2026 às 04:27:45 UTC, /mapa-ia/planos/ respondeu 200, text/plain, 1.737 bytes. /admin/documentos/ e /admin/documentos/novo responderam 302 para login. O inventário de navegador disponível estava vazio. Não houve escrita pelo editor nem desvio de autenticação. O editor administrativo armazena documentos no banco, com histórico próprio; o pacote Git usa a publicação de planos já existente.

Após a integração, a verificação deste artefato deve conferir status/conclusion do deploy, GET anônimo do endereço .md, presença no índice e bytes comparados com git show do commit integrado. Esse resultado posterior será registrado no corpo do PR 1382 e no livro, sem uma alegação circular de autoverificação dentro do próprio documento.

Para ci/, a entrega de código é no Git: conferir os arquivos do SHA integrado e executar o CLI nessa revisão. Para recibos mostrados no painel administrativo, confirmar deploy não basta: a prova aplicável exige leitura autenticada da tela e do livro mensal. Redirecionamento de login é limite de acesso, não publicação verificada; o mapa público não substitui essa tela. Nenhuma exceção de autenticação foi aberta.

## O que permanece pendente neste retrato

F1-05 aguarda commit/SHA do retrato, último fechamento focal e revisão independente do diff documental. F1-06 aguarda confirmação das integrações restantes, deploys aplicáveis e comportamento publicado com provas próprias. O PR 1383 já está integrado em 075d3b46 com deploy com sucesso confirmado; PR 1382 permanece aberto. O código aprovado e as provas amplas/retomadas não encerram sozinhos a Fase 1.

Abertura continua por make sessao; contexto adicional por ci/sessao.py --contexto; fechamento por make pr; CONTINUAR=1 retoma consultando os efeitos anteriores e exigindo validação atual. O mesmo JSON configura prazo_segundos entre 1 e 7200, padrão 900 por comando; as amplas escolheram 1800. TIMEOUT mantém a prova incompleta e exige reexecução.

Não aplicável requer declaração justificada. Ausência de evidência não recebe esse estado por inferência. Eficiência permanece não comprovada porque não há amostra de tarefas comparáveis nem linha de base adequada para ganho global.
