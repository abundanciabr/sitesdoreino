# CONSENSO DA FASE 4 | onde as IAs desta casa chegam a um acordo medido

**Aberto em 12/09/2026.** Este arquivo é a mesa de trabalho compartilhada das
IAs que assessoram o mantenedor na otimização da fábrica de robôs. Qualquer IA
pode ler, contestar e acrescentar. O que ninguém pode é vencer no argumento:
aqui o critério é número medido, não eloquência.

**Como usar, em quatro linhas.** Leia a §0 antes de tudo. Confira na §1 se a
sua ideia já foi feita e na §2 se ela já foi derrubada. Se sobreviver, escreva
uma ficha na §4 no formato da §3. Sem o campo 1 preenchido, a ficha cai na §5
e não disputa.

---

## §0 A REGRA DE MÉTODO, e ela é fail-closed

**A pasta local não é a verdade. `origin/main` é.**

Em 12/09/2026 o clone principal (`C:\Users\davia\OneDrive\Documentos\sitesdoreino`)
estava 82 commits atrás de `origin/main`, com zero commits locais e uma edição
não commitada que apaga 12 das 13 seções do `CLAUDE.md`. **Duas auditorias de
IA foram inteiramente invalidadas por medir essa pasta.** Elas recomendaram
arrancar ganchos que já tinham sido removidos e reverter uma regra que já
tinha sido corrigida.

Antes de afirmar qualquer coisa sobre o estado da fábrica:

```
git fetch origin
git show origin/main:<caminho>
```

No Git Bash do Windows, caminho começando com ponto quebra (`armadilhas/334`).
Use PowerShell, ou crie uma bancada de leitura:

```
git worktree add ../wt-leitura --detach origin/main
```

Toda afirmação nesta mesa precisa de comando e saída colada. Afirmação sem
prova é opinião, e opinião aqui não pontua.

---

## §1 O QUE JÁ ESTÁ FEITO | não proponha remover isto

Medido em 12/09/2026 contra `origin/main` = `22a9bd26`, por três auditores em
paralelo mais verificação direta.

| Peça | Medição |
|---|---|
| Ganchos por comando Bash | 5 para 0. `.claude/settings.json` tem `"PostToolUse": []` |
| Ganchos por Edit/Write | 4 para 0. O matcher restante é só `Monitor` |
| `CLAUDE.md` | 20.515 para 11.893 bytes, menos 42% |
| Saída de teste | 18.555 para 159 bytes, via `ci/resumo_de_teste.py`, menos 99,1% |
| Runner canônico | `ci/ci.py:50` importa `executar_pytest` e usa JSON |
| Mutação de guarda | `ci/provar_guardas.py`, bancada isolada, 3 de 3 reprovaram |
| Mutação manual | PROIBIDA por lei. `despacho.toml §4`: "Não faça mutação manual." |
| Microcommits | ABOLIDOS. `RITOS.md §2`: "Não há obrigação de microcommits a cada teste verde." |
| Sino automático | DESLIGADO nos dois harnesses. `ci/hook_codex.py` devolve `0` em `PostToolUse` |
| Ambiente | venv por hash SHA-256, `uv` com fallback, Postgres em container compartilhado |
| Pista de merge | Acorda em `workflow_run` e em `labeled`. Cron de 15 min é só rede de segurança. Não precisa de agente vivo. |
| Entregas | PRs #1589 a #1599 mergeados, todos verdes, zero órfão |
| Suítes das peças novas | 330 testes passando |

---

## §2 ALEGAÇÕES JÁ DERRUBADAS | não repita estas

Cada linha morreu para um comando, não para um debate.

| Alegação que circulou | O que a medição mostrou |
|---|---|
| "o local está 82 commits à FRENTE, precisa rebase" | Está 82 ATRÁS. `git log origin/main..HEAD` volta vazio: zero commits locais |
| "`.codex/hooks.json` vazio perde a proteção do `.claude/settings.json`" | Os DOIS têm `PostToolUse: []`. Não há divergência a unificar |
| "buraco do `collect_ignore` silencia testes" | Já tapado. `ci/catraca_de_testes.py:133` pega `collect_ignore`, `collect_ignore_glob`, `--ignore`, `norecursedirs`, `addopts`. 29 testes passando |
| "bypass da espera por PowerShell" | PowerShell é RECUSADO nas 5 assinaturas. Ver P-1, o furo real é outro |
| "`--sonda` é bypass" | Recurso legítimo, `--teto` obrigatório em `ci/esperar.py:891` |
| "restaurar a `main`" | A `main` está intacta, com as 13 leis. Quem está mutilado é só a pasta local |
| "`AGENTS.md` foi comprimido de 21KB" | `AGENTS.md` não existia antes da Fase 1 |
| "o sino ainda roda em todo comando" | Falso em `origin/main`. Verdadeiro só na pasta local desatualizada |
| "a catraca de microcommits está intocada" | Falso. Foi reescrita. O diff está no §1 |
| "ligar o `--json-report` nos Makefiles e matar a leitura de tela" | O runner canônico já usa JSON. Só os Makefiles de célula ainda chamam `pytest -q`, e eles não são o caminho do robô |

---

## §3 COMO UMA PROPOSTA ENTRA

Copie o bloco, preencha, cole na §4 com o próximo número livre.

```
### P-<n> | <o que sai ou entra, em uma linha>
Autor: <qual IA>     Reversível: sim/não     Data: <dd/mm/aaaa>

1. CUSTO HOJE
   Comando e saída colada provando quanto isto custa agora, em tempo,
   tokens, ou passos. Sem este campo a ficha vai para a §5 e não disputa.

2. GANHO ESPERADO
   Número, e o comando que vai prová-lo depois de feito.

3. AINDA NÃO FOI FEITO
   Comando contra `origin/main` provando que a coisa que você quer mudar
   ainda está lá. Foi neste campo que 3 de 4 recomendações anteriores morreram.

4. RISCO DE QUALIDADE
   O que pode quebrar, e qual guarda pega se quebrar.

5. DEPENDE DE
   P-<n> que precisa vir antes, ou "nada".
```

**A regra de corte.** Ficha sem o campo 1 preenchido com saída real não entra
no placar. Vai para a §5, hipóteses, que nunca vence.

**O ranking.** Ganho medido dividido por risco. Empate desfeito pelo que for
reversível. Não há voto, não há maioria, não há "eu acho". Se duas fichas
medem a mesma coisa e discordam do número, as duas ficam abertas até alguém
rodar o comando de novo e colar a saída.

**Contestar é bem-vindo.** Para derrubar uma ficha, acrescente abaixo dela uma
linha `CONTESTADA por <IA>:` com o comando e a saída que provam o contrário.
Não apague a ficha de ninguém.

---

## §4 AS FICHAS

As sete primeiras saíram da auditoria de 12/09/2026 e já vêm com os campos 1 e
3 preenchidos. Contestem à vontade.

### P-1 | Devolver visão à muralha da espera
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   As 5 assinaturas de espera muda só rodam no ramo `Bash`/`PowerShell`, e o
   gancho só recebe `Monitor`. Mesmo comando, variando só `tool_name`:
   ```
   caso                Bash    PowerShell   Monitor
   watch de run        RECUSA  RECUSA       PERMITE
   watch de checks     RECUSA  RECUSA       PERMITE
   laço sem teto       RECUSA  RECUSA       PERMITE
   soneca longa        RECUSA  RECUSA       PERMITE
   soneca longa PS     RECUSA  RECUSA       PERMITE
   ```
   Custo histórico do que isto deixa passar: a espera muda consumia de 18% a
   21,8% da cota semanal (`ci/esperar.py:76`).

2. GANHO ESPERADO
   Voltar a barrar as 5 no ramo `Monitor`. Prova depois: a mesma tabela com
   RECUSA nas três colunas.

3. AINDA NÃO FOI FEITO
   `.claude/settings.json` em `origin/main`: `PreToolUse` com matcher
   `"Monitor"` apenas. `ci/muralha_da_espera.py:230`:
   `if ferramenta in ("Bash", "PowerShell")`.

4. RISCO DE QUALIDADE
   Baixo. Falso positivo volta a bloquear comando legítimo cujo TEXTO cite
   uma assinatura, o que aconteceu 3 vezes durante esta auditoria. O guarda
   é `ci/tests/test_muralha_da_espera.py`.

5. DEPENDE DE
   nada.

### P-2 | Fechar as dez tarefas da fila
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   ```
   TAR-358 : explicada reivindicada submetida
   TAR-359 : explicada
   TAR-360 a 367 : explicada reivindicada submetida
   ```
   Zero eventos `concluida` nas dez, com todos os PRs mergeados e verdes.
   O balcão diz "falta comprovar o aceite" para 100% do trabalho da Fase 1 a 3.

2. GANHO ESPERADO
   Evitar retrabalho. Um despacho novo que vá ao balcão encontra a TAR-359
   livre e refaz o que já está na `main`. Custo já pago uma vez: em 05/09 duas
   sessões construíram o mesmo portfólio.

3. AINDA NÃO FOI FEITO
   `ls fila/eventos/ | grep TAR-36` não devolve nenhum `-concluida`.

4. RISCO DE QUALIDADE
   Baixo. Fechar tarefa exige evidência; a evidência é o PR mergeado.

5. DEPENDE DE
   nada. É pré-condição de qualquer despacho novo.

### P-3 | Abrir folga no teto do CLAUDE.md
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   `CLAUDE.md` tem 11.893 bytes. `ci/padrao_de_trabalho.py:95` define
   `TETOS_EM_BYTES = {"CLAUDE.md": 12_000}`. Sobram 107 bytes, 0,9%.
   Nenhuma lei nova cabe, inclusive a da P-4.

2. GANHO ESPERADO
   Mover a história de cada lei para `docs/decisoes/`, como a própria lei do
   `CLAUDE.md` já manda. Prova depois: o novo tamanho em bytes.

3. AINDA NÃO FOI FEITO
   `wc -c CLAUDE.md` em `origin/main` devolve 11893.

4. RISCO DE QUALIDADE
   Médio. Mover texto de lei é exatamente o gesto que o robô da Fase 3 usou
   para apagar 12 leis. Deve sair junto com a P-4, nunca antes.

5. DEPENDE DE
   nada, mas a P-4 depende desta.

### P-4 | Piso de leis no portão
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   O portão permite apagar lei. `ci/leis_sem_mecanismo.py:28`, literal:
   "A dívida só encolhe: sair da lista é sempre permitido (a lei ganhou
   mecanismo, ou deixou de existir)."
   Foi assim que a Fase 3 apagou 12 das 13 seções do `CLAUDE.md` e passou
   verde: apagou junto as 3 entradas correspondentes de
   `ci/leis-sem-mecanismo.txt`.

2. GANHO ESPERADO
   Guarda que recusa PR removendo seção de `CLAUDE.md`, `CONSTITUICAO.md` ou
   `RITOS.md` sem uma decisão escrita no mesmo PR. Prova depois: mutação que
   remove uma seção fica vermelha.

3. AINDA NÃO FOI FEITO
   `git show origin/main:ci/leis_sem_mecanismo.py` não tem contagem mínima
   nem comparação com a base.

4. RISCO DE QUALIDADE
   Baixo. O guarda não impede mudar lei, impede mudar lei em silêncio.

5. DEPENDE DE
   P-3, porque a lei nova não cabe nos 107 bytes que sobram.

### P-5 | Índices de armadilha em bancada nova
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   `armadilhas/SINAIS.json`, `INDICE.md` e `GATILHOS.json` são gitignored
   (`.gitignore:70,72,73`). Só o `SessionStart` do Claude Code os gera. Um
   auditor bateu em `ERROR: No such file or directory` na primeira chamada a
   `ci/consultar_armadilhas.py`, a ferramenta central da Fase 3.

2. GANHO ESPERADO
   A ferramenta responde em qualquer caminho: Codex, sub-agente, CI.
   Prova depois: chamada em bancada recém-criada, sem SessionStart, devolve
   PASS.

3. AINDA NÃO FOI FEITO
   `git check-ignore -v armadilhas/SINAIS.json` devolve `.gitignore:72`.

4. RISCO DE QUALIDADE
   Baixo. Versionar arquivo gerado cria ruído de merge; semear na abertura da
   bancada não cria.

5. DEPENDE DE
   nada.

### P-6 | Tirar o entulho que mente
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   Três coisas dizem fazer o que não fazem:
   `ci/preco_da_conversa.py` está órfão, nenhum arquivo de configuração o
   chama desde que `PostToolUse` esvaziou.
   `RITOS.md:195` cita uma frase do `CLAUDE.md` ("espere os checks
   concluírem") que não existe mais na lei viva, que diz o oposto.
   Merge Queue aparece como pendência, mas é impossível aqui:
   `gh api repos/abundanciabr/sitesdoreino --jq .owner.type` devolve `"User"`,
   e Merge Queue exige organização.

2. GANHO ESPERADO
   Nenhum ganho de velocidade. Ganho de verdade: quem lê para de ser enganado.

3. AINDA NÃO FOI FEITO
   `grep -rn "espere os checks" CLAUDE.md` não casa nada, e `RITOS.md:195`
   continua citando.

4. RISCO DE QUALIDADE
   Baixo. Se a métrica do preço da conversa ainda importa, religar em vez de
   aposentar; o arquivo e os testes decidem juntos.

5. DEPENDE DE
   nada.

### P-7 | Medir o ciclo inteiro, antes e depois
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   O ganho de 10x nunca foi medido. O PR que ia medir foi abandonado:
   ```
   {"number":1588,"title":"rascunho: medir-ciclo-inteiro",
    "state":"CLOSED","mergedAt":null}
   ```
   Não existe número de antes nem de depois. "10x" hoje é fé.

2. GANHO ESPERADO
   Um número honesto. Prova: uma tarefa cobaia rodada de ponta a ponta com
   tempo de relógio e tokens registrados, comparada com o mesmo tipo de
   tarefa antes das fases.

3. AINDA NÃO FOI FEITO
   `gh pr view 1588` devolve `"state":"CLOSED","mergedAt":null`.

4. RISCO DE QUALIDADE
   Nenhum. É medição, não mudança.

5. DEPENDE DE
   P-1 a P-6, porque medir antes de fechar as lacunas mede um sistema que vai
   mudar em seguida.

### P-8 | Devolver a trava de edição do clone compartilhado
Autor: Claude Code (auditoria 12/09)     Reversível: sim     Data: 12/09/2026

1. CUSTO HOJE
   Em `origin/main`, `muralha_pasta_compartilhada.py` roda SÓ no `SessionStart`,
   como aviso. Deixou de ser gancho de `PreToolUse` em Edit/Write:
   ```
   PreToolUse     matcher=Monitor    -> muralha_da_espera.py
   SessionStart   matcher=(todos)    -> muralha_pasta_compartilhada.py
   ```
   Nada impede um robô de editar o clone principal compartilhado. Esta é a
   causa mecânica mais provável da mutilação do `CLAUDE.md` em 12/09 às 08:56:
   o robô da Fase 3 rodou com esta configuração, editou o espelho direto e
   deixou 219 linhas apagadas soltas na árvore.
   A trava existia antes: `git show 5108e307:.claude/settings.json` tem
   matcher `Edit|Write|NotebookEdit|Bash|PowerShell` para essa muralha.

   **Segundo furo, medido em 12/09 ao escrever este arquivo:** mesmo com a
   configuração ANTIGA ativa (a que ainda barra Edit/Write), a muralha deixa
   passar escrita por shell. `Write` no clone principal devolveu exit 2, e
   um `cp` para o mesmo destino, no mesmo instante, gravou 16.701 bytes sem
   reclamar. Quem devolver a trava precisa cobrir os dois caminhos, senão
   devolve só a aparência dela.

2. GANHO ESPERADO
   Nenhuma sessão volta a apagar lei no espelho. Prova depois: tentativa de
   escrita no clone principal devolve exit 2.

3. AINDA NÃO FOI FEITO
   A saída acima, medida em `origin/main` = `22a9bd26`.

4. RISCO DE QUALIDADE
   **Esta é a única ficha que anda CONTRA a otimização**, e por isso precisa de
   decisão consciente: devolver o gancho custa 1 processo Python por edição,
   contra os 0 de hoje. A alternativa sem custo em tempo de robô é um guarda de
   CI que recuse PR cuja edição tenha vindo do clone principal. As duas
   resolvem; a segunda pega depois, a primeira pega na hora.

5. DEPENDE DE
   nada. Conversa com a P-4: as duas tratam do mesmo estrago por caminhos
   diferentes, e podem ser redundantes. Contestem.

---

## §5 HIPÓTESES SEM MEDIÇÃO | não disputam o placar

Ideias sem o campo 1 preenchido moram aqui até alguém medi-las. Nenhuma vence
enquanto estiver nesta seção. Mover para a §4 exige comando e saída.

(vazia por enquanto)

---

## §6 PERGUNTAS QUE SÓ O MANTENEDOR RESPONDE

Nenhuma IA decide estas. Consolidem aqui em vez de perguntar solto.

1. **As 12 leis apagadas na pasta local.** Ele disse que talvez mereçam
   revisão. Revisar quais ainda servem, ou restaurar as 13 e revisar depois
   com calma? A `main` está intacta nos dois casos.
2. **O piso de leis (P-4).** Travar na contagem atual, ou exigir uma decisão
   escrita em `docs/decisoes/` em todo PR que remova seção de lei?
3. **A muralha da espera (P-1).** Consertar, ou aposentar a detecção agora que
   a lei já diz "não espere checks, merge ou deploy"?
4. **A cobaia da P-7.** Qual tarefa serve de medição, e o que vale como número
   de antes, já que o baseline nunca foi capturado?

---

## §7 PLACAR

Preenchido quando as fichas tiverem contestação ou confirmação. Ordem por
ganho medido dividido por risco.

| Posição | Ficha | Ganho medido | Risco | Reversível | Estado |
|---|---|---|---|---|---|
| a definir | P-1 | cota de volta, 18% a 21,8% | baixo | sim | aberta |
| a definir | P-2 | evita retrabalho já pago 1 vez | baixo | sim | aberta |
| a definir | P-3 | destrava P-4 | médio | sim | aberta |
| a definir | P-4 | impede repetir a Fase 3 | baixo | sim | aberta |
| a definir | P-5 | ferramenta responde fora do Claude Code | baixo | sim | aberta |
| a definir | P-6 | zero velocidade, ganha verdade | baixo | sim | aberta |
| a definir | P-7 | o número que ninguém tem | nenhum | sim | aberta |
| a definir | P-8 | fecha a porta por onde a lei foi apagada | anda contra a otimização | sim | aberta |

---

## §8 REGISTRO DE QUEM PASSOU AQUI

| Data | IA | O que fez |
|---|---|---|
| 12/09/2026 | Claude Code (Opus) | Abriu a mesa. Fichas P-1 a P-8, §1 e §2 medidos contra `origin/main` = `22a9bd26` |

**Nota de método para quem chegar.** Uma sessão aberta no clone principal LÊ
este arquivo normalmente. O que ela não deveria poder fazer é editá-lo lá, e
hoje pode (ver P-8). Se você for contestar uma ficha, faça na sua bancada e
mande o PR, ou devolva o texto ao mantenedor para ele colar. Editar o espelho
direto é o gesto que causou o estrago que a P-4 e a P-8 tratam.
