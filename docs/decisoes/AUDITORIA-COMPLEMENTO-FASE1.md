---
publico-para-ia: true
---

# Auditoria do complemento da Fase 1

## Veredito deste retrato

**PARCIAL.** Há correções implementadas e provas focais, mas a validação ampla do fechamento corrigido e o parecer independente do conjunto final ainda não terminaram. Este documento não declara a Fase 1 concluída. Integração das correções e publicação deste pacote permanecem pendentes. Ganho de eficiência não comprovado.

Este é um retrato da auditoria em 08/09/2026, vinculado às revisões abaixo, e não uma nova fonte de estado operacional. PRs, runs e livro de ocorrências continuam sendo as fontes dos estados vivos. Uma conclusão posterior exige nova prova e atualização explícita do retrato; a existência deste arquivo não comprova seu deploy.

A missão corretiva atual é a autoridade para F1-01 a F1-06. As emendas das Leis 2 e 4 da CONSTITUICAO orientam abrangência de células e integração pela pista. Os documentos históricos permanecem preservados.

## Revisões e alcance

| Parte | Revisão examinada | Limite da prova |
|---|---|---|
| Base integrada | 87365d3234fdb2ea3543986d80ba196ba36f36f3 | Estado anterior ao complemento |
| Contexto e instruções, código | d24e0aac0af7c661ccb14026642690ec40a8049d | 15 arquivos de código e receitas |
| Contexto e instruções, com recibo | fbc4520cea95e1316a2143b52ebf22d13effa1ae | [PR 1381](https://github.com/abundanciabr/sitesdoreino/pull/1381); diferença posterior ao código: somente recibo de 977 bytes |
| Prazo de validação | 041ddea25e6bc938a2025699f89eecb377ee4a25 | Commit de 08/09/2026 às 04:28:20 UTC; fechamento amplo ainda em execução |
| Cobertura individual | Bancada de coordenação sobre 87365d3234fdb2ea3543986d80ba196ba36f36f3 | Alteração ainda sem commit neste retrato; hashes abaixo identificam os arquivos examinados |

## Matriz F1-01 a F1-06

| ID | Problema confirmado | Correção ou prova vigente | Estado neste retrato |
|---|---|---|---|
| F1-01 | Pacote, ficha e receitas ainda exigiam índice integral | Índice virou aprofundamento; recuperação por caminho e sintoma preserva leis, origens, ausência e truncamento; 245 testes e pilotos reais; 17 mutações | Implementado e testado no PR 1381; integração pendente |
| F1-02 | Receitas manuais, escrivão redundante e cópias locais contraditórias | Fontes rastreadas conciliadas; três instruções locais ajustadas com backup e hashes; reserva e recibo ficam no make pr; merge é da pista | Alterações demonstradas; parecer do conjunto final pendente |
| F1-03 | Prazo fixo de 300 segundos podia interromper suíte maior | JSON existente aceita prazo_segundos inteiro de 1 a 7200; padrão de 900 por comando; timeout distinto de falha; encerramento de descendentes e retomada testados em Windows e Linux | 88 testes Windows, 27 Linux e 7 mutações; suíte ampla corrigida pendente |
| F1-04 | Presença global de fases podia parecer completude de tarefa | Consolidação por tarefa, tentativa, ramo e revisão; observações sucessivas preservadas; publicação correlacionada por PR e revisão sem transplantar a fase para a sessão local | 61 testes focais; 6 mutações; dois achados de revisor corrigidos; validação composta pendente |
| F1-05 | Aprovação narrada não bastava para auditoria externa | Este pacote apresenta matriz, quinze respostas, revisões, comandos, trechos reais e links públicos; revisão separada identificada abaixo | Parecer independente final e publicação do pacote pendentes |
| F1-06 | Integração, deploy e comportamento publicado estavam misturados | Cinco PRs anteriores e seus deploys foram conferidos; mapa público comparado por bytes; correções atuais mantêm estados separados | Histórico comprovado no alcance declarado; integração e publicação do complemento pendentes |

## As quinze perguntas obrigatórias

1. **O percurso foi automatizado ou apenas mudou etapas manuais de lugar?** Abertura usa ci/sessao.py; fechamento usa ci/pr.py. O piloto do PR 1381 criou ou retomou a bancada, emitiu contexto, validou duas revisões isoladas e embarcou o recibo. A retomada reexecutou as provas e manteve um PR e um recibo. As receitas antigas de preparação e escrituração foram retiradas das fontes ativas identificadas. O conjunto final ainda precisa do piloto composto.

2. **Alguma ferramenta ou função existente foi duplicada?** As correções se concentram em ci/sessao.py, ci/pr.py e consolidar_percurso(), sem novo executor externo, orquestrador, painel ou fila. O encerramento de processos pertence ao runner existente. O pacote público usa a rota de planos já implantada.

3. **As contradições foram resolvidas por autoridade rastreável?** Sim, no alcance inspecionado: missão corretiva de 08/09/2026 e emendas da CONSTITUICAO Leis 2 e 4. Uma célula por PR é preferência com suítes de todas as tocadas, e só a pista executa merge. Arquivos locais foram ajustados separadamente, sem serem apresentados como efeito do PR.

4. **Alguma instrução ativa ainda exige o procedimento antigo?** Os testes do PR 1381 percorrem oito fontes de contexto, três de escrituração e quatro receitas de abertura; a obrigação conhecida foi retirada. AGENTS.md e duas fichas Codex locais foram corrigidos com manifesto. 00-LEIA-PRIMEIRO é história declarada pelo PLAYBOOK; RUNBOOK §9 conserva relatos históricos. Isso não certifica máquinas ou instruções que não foram inspecionadas, nem substitui o parecer final do conjunto.

5. **O contexto direcionado pode omitir regras obrigatórias?** Não houve dispensa das leis: o pacote continua indicando CLAUDE/AGENTS presentes, CONSTITUICAO, RITOS, Retrospectiva, Constituição da célula, LICOES e AGENTS dos caminhos. Fontes ausentes são avisadas. Um teste impede ler o índice sentinela e exige leis no pacote; outros conferem gatilho transversal, múltiplos alvos e regra real 394. Uma lista de referências não prova que um agente leu os documentos.

6. **A telemetria distingue mensagens, ferramentas, tarefas e tentativas?** Os mecanismos existentes de uso permanecem; o complemento distingue namespace da tarefa, tentativa, ramo, revisão e entrega. A presença global é identificada como presença_global, sem equivaler à completude individual. Os testes focais passaram; a regressão ampla da versão corrigida permanece pendente.

7. **A deduplicação ou agregação pode produzir contagens incorretas?** Foram reproduzidos dois falsos resultados quando uma identidade reaparecia: reinício após conclusão parecia concluído, e nova aprovação após falha parecia falha. A correção preserva observado_em e avalia as observações mais recentes. Eventos repetidos, tarefas e tentativas distintas são testados; as seis mutações de cobertura reprovaram. Não se declara impossibilidade universal de defeito.

8. **O fechamento aceita prova ausente, antiga ou de outra revisão?** O mecanismo exige configuração de validação, executa em worktree isolado do commit, recusa caminhos absolutos de scripts e confere a revisão final após recibo. Timeout não produz aprovação e exige nova validação. O PR 1381 provou o mesmo SHA no GitHub; a versão nova do prazo tem testes focais, mas a execução ampla ainda não terminou.

9. **A retomada pode duplicar efeitos?** O piloto real de contexto concluiu com um PR e um recibo de 977 bytes após --continuar. A reserva usa identidade estável, e o comando consulta o PR e os eventos existentes. Esse piloto não tinha tarefa da fila, portanto não prova sozinho a deduplicação de evento da tarefa; a prova composta com fila permanece pendente. Testes controlados do prazo exigem duas novas provas após timeout.

10. **Existe caminho que contorne revisão ou permissões?** A correção retira --confirmo do molde de agente e mantém a pista como integradora. Não foi criado bypass de autenticação. O GET anônimo da área administrativa retorna login; isso não foi tratado como sucesso da tela. Revisão independente permanece uma obrigação separada do comando de fechamento.

11. **As mudanças invadiram as fases 2 ou 3?** O diff declarado cobre contexto, instruções, prazo do fechamento, cobertura de métricas e evidências. Não separa publicação de registros, não cria outbox compartilhado e não altera arquitetura de células, bancos, infraestrutura ou seleção de modelos.

12. **Algum teste ou controle foi enfraquecido?** Os controles de revisão, baseline, erro de instrumento, reserva, recibo e integração permanecem. A ampliação de prazo tem teto finito e entrada validada; não fragmenta a suíte. O teto de CLAUDE acusou a primeira redação, e somente o texto adicionado foi condensado para respeitá-lo. Mutações foram restauradas. A conclusão global depende da revisão do diff consolidado e da suíte final.

13. **Logs e recibos expõem informações sensíveis?** Este pacote publica somente revisões, comandos, hashes, resultados e conteúdo sanitizado. Não publica transcrições de sessão, cookies, credenciais, caminhos pessoais ou conteúdo de backups globais. O PR 1381 contém as saídas necessárias, e seu corpo foi relido integralmente. Constantes dos testes de segredo são dados artificiais, não credenciais; os logs integrais privados não são copiados indiscriminadamente.

14. **As alegações de eficiência têm medição válida?** Há tempos reais de testes e bytes emitidos pelos pilotos. Não há vinte tarefas comparáveis nem linha de base retroativa adequada para comprovar ganho global. Bytes não foram convertidos em tokens, e deduplicação não foi chamada de economia de consumo. Ganho de eficiência: não comprovado.

15. **Um agente novo consegue executar o fluxo pela documentação atual?** O piloto do PR 1381 executou abertura e contexto reais, e o fechamento com retomada concluiu. As fontes conhecidas e três instruções locais foram alinhadas. Ainda falta encerrar a auditoria independente e a execução composta das correções; portanto, este retrato não certifica o fluxo consolidado para qualquer nova sessão.

## Provas executadas e comandos

Ambiente do contexto: Windows 11, Python 3.12.10. Provas completas do contexto estão no [corpo público do PR 1381](https://github.com/abundanciabr/sitesdoreino/pull/1381), inclusive comandos, horários UTC, vermelho, mutações e saídas dos pilotos.

| Comando ou ensaio real | Revisão | Resultado |
|---|---|---|
| python -m pytest ci/tests/test_sessao.py ci/tests/test_sessao_contexto.py ci/tests/test_sessao_retomada.py ci/tests/test_fichas_de_robo.py ci/tests/test_indice_de_armadilhas.py -q | Base 87365d32, antes das edições | 182 passed in 13.90s |
| python -m pytest ci/tests/test_sessao_contexto.py ci/tests/test_fichas_de_robo.py -q | Novos guardas antes da correção | 5 failed, 31 passed in 3.95s |
| Suíte ampliada de contexto, comando abaixo, em worktree isolado | fbc4520cea95e1316a2143b52ebf22d13effa1ae | 245 passed in 23.39s |
| python ci/indice_de_armadilhas.py | Mesmo SHA isolado | PASS, 375 entradas |
| python ci/travessao.py | Mesmo SHA isolado | PASS, 167 arquivos inspecionados; dívida herdada estável |
| python -m pytest ci/tests/test_pr.py -q | 041ddea25e6bc938a2025699f89eecb377ee4a25, Windows | 88 passed in 11.34s |
| Seleção Linux de prazo, timeout e instrumento, comando abaixo | Mesmo código, montagem somente leitura | 27 passed, 61 deselected in 8.52s |
| python -m pytest ci/tests -q -n 4 | Base anterior ao fix de prazo | 2334 passed in 457.98s; NÃO é prova da revisão corrigida |
| Mesmo comando amplo pelo ci/pr.py, prazo_segundos 1800 | Correção de prazo | Execução em andamento; nenhum resultado final aprovado neste retrato |
| python -m pytest ci/tests/test_metricas_percurso.py ci/tests/test_metricas_da_fabrica.py -q | Bancada de métricas, hashes abaixo | Baseline 48 passed in 9.16s; após correções 61 passed in 2.02s e 2.33s, informado pela maestro |
| Reexecuções separadas do revisor | Métricas e guardas adicionais na bancada | 60 passed in 2.03s e 61 passed in 2.27s, informado pelo revisor à maestro |

Suíte ampliada de contexto realmente executada:

```text
python -m pytest ci/tests/test_sessao.py ci/tests/test_sessao_contexto.py ci/tests/test_sessao_retomada.py ci/tests/test_fichas_de_robo.py ci/tests/test_indice_de_armadilhas.py ci/tests/test_indice_com_a_origem.py ci/tests/test_padrao_de_trabalho.py ci/tests/test_licao_do_caminho.py -q
```

Seleção Linux realmente executada, com o caminho pessoal da montagem substituído por BANCADA nas evidências públicas:

```text
docker run --rm --network none --mount "type=bind,source=BANCADA,target=/repo,readonly" --workdir /repo --entrypoint python ghcr.io/abundanciabr/plataforma-checkout:14be60c6359b9c7c9a37242822c36bf319c01cba -m pytest ci/tests/test_pr.py -q -k "prazo or timeout or instrumento" -p no:cacheprovider
```

A imagem de checkout foi usada como ambiente Linux já disponível; isso não é teste da célula de pagamentos ou mudança no produto checkout. Datas sem carimbo interno em logs não são convertidas em horários exatos de execução. O baseline amplo tem início/fim reconstruídos pela sessão; somente seu resultado e a duração impressa são tratados como saída direta do teste.

## Achados e mutações

Revisão independente foi executada por /root/auditoria, papel revisor, em recurso separado de colaboração. Não é troca de persona do implementador. A análise do estado consolidado ainda aguarda as revisões finais; os resultados abaixo são os achados focais comunicados pela maestro.

| Achado | Reprodução e local | Correção e reteste | Estado |
|---|---|---|---|
| Reabertura aparecia concluída | consolidar_percurso(): fechamento iniciado às 00:01, concluído às 00:02 e reiniciado às 00:03 retornava concluído | Últimas observações preservadas; test_reinicio_de_fechamento_na_mesma_identidade_nao_fica_concluido | Corrigido na bancada; severidade final ainda não informada |
| Nova aprovação permanecia falha | Validação concluída às 00:00, falhou às 00:01, concluída às 00:02 retornava falha | observado_em preserva transições; test_revalidacao_observada_apos_falha_preserva_transicoes | Corrigido na bancada; severidade final ainda não informada |
| Índice obrigatório | Obrigatórias continham armadilhas/INDICE.md e receitas repetiam a ordem | Cinco novos guardas nasceram vermelhos; 245 testes verdes | Corrigido no PR 1381 |
| Teto de instrução excedido | Primeira redação de CLAUDE atingiu 20.221 caracteres para teto de 20.000 | Condensado somente texto adicionado; teste do Padrão passou | Corrigido no PR 1381 |
| Leitura remota ainda não confirmava o SHA | Primeiro fechamento do PR 1381 recusou ao conferir remoto | gh pr view e git ls-remote confirmaram OPEN e SHA final; --continuar revalidou e concluiu | Resolvido, sem novo recibo |

Trechos reais da evidência, em vez de apenas nomes de testes:

```text
Contexto antes da correção:
AssertionError: assert 'INDICE.md' not in 'Leituras obrigatórias: ...'
5 failed, 31 passed in 3.95s

Mutação de repetição temporal:
assert not r["por_tentativa"][0]["percurso_local_concluido"]
E assert not True
2 failed, 42 deselected in 0.13s

Mutação de publicação transplantada para a sessão:
assert local["fases"]["publicacao"]["estado"] == "sem_evidencia"
E AssertionError: assert 'verificado' == 'sem_evidencia'
1 failed, 43 deselected in 0.13s

Prazo antes da correção:
24 failed, 60 deselected in 0.79s

Prazo depois da correção, Windows:
88 passed in 11.34s

Prazo depois da correção, Linux:
27 passed, 61 deselected in 8.52s
```

As saídas acima são recortes identificados; o recorte abreviado de contexto não se apresenta como log integral. As mutações são ensaios controlados, com sabotagem restaurada, e não defeitos deixados no código entregue.

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

## Percurso operacional observado

No PR 1381, a abertura real inicialmente recusou bancada suja e preservou os arquivos. Depois do commit, a mesma entrada concluiu com exit 0. Como os alvos não são serviço, --sem-container declarou baseline não medido; testes dos caminhos foram executados separadamente.

```text
python ci/sessao.py --celula ci --tarefa contexto-correcao-f1 --sem-container --frase "Corrigir instruções e contexto da Fase 1" --caminho ci/sessao.py --caminho painel/registros/teste.js --sintoma "git status limpo sem ninguem ter medido" --aceite "Índice apenas para aprofundamento"
```

O pacote emitiu como obrigatórias CLAUDE.md, CONSTITUICAO.md, RITOS.md e docs/decisoes/RETROSPECTIVA-FASE-D.md. O índice apareceu somente como aprofundamento. Os quatro pilotos de contexto produziram: múltiplos alvos, 5.623 bytes e lições 179/373; vazio, 689 bytes com ausência explícita; limite 1, 2.291 bytes e truncamento; limite 100, 3.837 bytes sem truncamento. Essas medidas pertencem a consultas diferentes, não constituem antes/depois comparável.

O fechamento executou índice, suíte ampliada e travessão na revisão do código e na revisão com recibo. A retomada --continuar terminou com:

```text
PASS validação local concluída; recibo embarcado e revisão remota conferida
Revisão: não verificada. Integração: não verificada. Publicação: não verificada.
PR 1381 aberto com recibo: https://github.com/abundanciabr/sitesdoreino/pull/1381
exit 0
```

O texto abreviado acima conserva a separação de estados da saída. Um único recibo novo foi contado, e gh pr view confirmou OPEN com fbc4520cea95e1316a2143b52ebf22d13effa1ae. A correlação completa do piloto composto, incluindo tarefa da fila e nova configuração de prazo, continua pendente; não é inferida do conjunto global de eventos.

## Instruções locais e origem das regras

CLAUDE.md e .claude/agents são rastreados. A Constituição rege as leis; RITOS, RUNBOOK, PLAYBOOK, ARMADILHAS, CAMINHO-DOURADO e os moldes são receitas. ci/sessao.py recupera contexto; ci/indice_de_armadilhas.py gera arquivos ignorados, que continuam acessíveis para aprofundamento.

A instalação local foi inspecionada pela maestro. AGENTS.md recebeu ajustes nas três seções de contexto, bancada e lote; as fichas despacho/revisor em .codex/agents tiveram developer_instructions alinhado à fonte .claude. Os demais campos TOML foram preservados por comparação estruturada. Não foi identificado gerador canônico de toda a instalação Codex. O script aplicado preservou backups, diffs e hashes antes/depois; os backups permanecem privados, sem publicação do conteúdo global.

| Arquivo local | SHA256 antes | SHA256 depois |
|---|---|---|
| AGENTS.md | 61d74c8f4d9df44f2a0a7383a22c748c36d69642bf61c13f4ef3cdb60d70050e | bd09dff48810146e085a6abbceba6c9c5cf0860ea646c9d1aa9be87bc9872a87 |
| .codex/agents/despacho.toml | d825bbb764c39d0bd5572f8c79d1daa2ff79bdbc995157f035c9b12b1bbb265d | 6fcf4bf07ec0b6e8085d0bd6700e521033eb2726d39b5ebf990c4b28ddf5d9f8 |
| .codex/agents/revisor.toml | 2f382c75a9880f89e837fbd9450ed63ab49f163f4fe295764db059ea2c6366d1 | d2ba23f9838d2f910d818bafc0c427190a42b1997bf40b12814decc8666d6418 |

Os hashes foram relidos e comparados aos três arquivos atuais nesta preparação. Um hash identifica os bytes; não substitui a inspeção que a maestro realizou. Estes ajustes não viajam no Git e não certificam outras instalações.

Hashes da revisão de métricas ainda sem commit:

| Arquivo | SHA256 |
|---|---|
| ci/metricas_da_fabrica.py | e29c9c4c74478874f4e5f8bf941405629cc67393703cef25e460bdd741634ca8 |
| ci/tests/test_metricas_percurso.py | 2178eb2a74f792ea3002d8b61232f9c95380398eab21c532dd3364abc5f6072c |

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

## Publicação e limitações de acesso

Este arquivo usa a rota existente /mapa-ia/planos/AUDITORIA-COMPLEMENTO-FASE1.md. docs/decisoes já é embutido na imagem de admin pelo deploy-celula. Nenhuma nova rota, regra de autenticação ou fonte de estado foi criada. A marca publico-para-ia é uma declaração explícita para publicar somente este conteúdo sanitizado.

Em 08/09/2026 às 04:27:45 UTC, /mapa-ia/planos/ respondeu 200, text/plain, 1.737 bytes. /admin/documentos/ e /admin/documentos/novo responderam 302 para login. O inventário de navegador disponível estava vazio. Não houve escrita pelo editor nem desvio de autenticação.

Verificação ainda exigida após integração deste pacote: GET anônimo do endereço .md, presença no índice e comparação de bytes com git show do commit integrado. O deploy deve ser conferido pelo status/conclusion do run correspondente. Para ci/, a publicação é no Git: conferir os arquivos do SHA integrado e executar o CLI nessa revisão. Para o painel administrativo, comprovar os recibos exige leitura autenticada da tela e do livro mensal; sem essa leitura, o comportamento publicado permanece não verificado.

## Uso do fluxo e limites restantes

Abertura: make sessao CELULA=<celula> TAREFA=<slug>, com TAR quando existir tarefa da fila. Contexto adicional: ci/sessao.py --contexto, com os caminhos e o sintoma. Fechamento: make pr com TITULO, MENSAGEM, CORPO, ARQUIVOS, DETALHE e VALIDACAO; CONTINUAR=1 retoma. Os arquivos de entrada seguem painel/LEIA-ME.md.

Na correção de prazo, o mesmo JSON de validação aceita prazo_segundos. O valor deve ser inteiro entre 1 e 7200; a ausência escolhe 900 por comando. A execução ampla atual escolheu 1800. TIMEOUT mantém a prova incompleta e exige reexecução; não autoriza recibo de sucesso nem reutilização silenciosa.

Pendências obrigatórias deste retrato: fechamento amplo corrigido, revisão independente do estado composto, piloto correlacionado do conjunto, integração das correções pela pista e publicação aplicável verificada. Não aplicável exige declaração e justificativa; ausência de evento não recebe essa classificação automaticamente. Eficiência continua não comprovada por falta de amostra comparável.
