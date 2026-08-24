# ARMADILHAS RESOLVIDAS — registro histórico

> Entradas que já foram **resolvidas de vez** e saíram da dieta de leitura do
> agente em 23/08/2026, quando o `ARMADILHAS.md` monolítico virou uma entrada por
> arquivo em `armadilhas/`. Elas continuam existindo aqui, **palavra por palavra
> como estavam** — resolvido não é apagado: o "era assim" explica por que o
> mecanismo de hoje tem a forma que tem, e é o que impede a mesma correção de ser
> refeita do zero.
>
> **Não leia isto num despacho normal.** O que vale para a próxima linha de código
> está em `armadilhas/INDICE.md`. Venha aqui só quando precisar do histórico de um
> item específico, ou quando uma referência antiga apontar para um `§` daqui.
>
> Cada título abaixo guarda o número que a entrada tinha no monólito, para que as
> referências antigas (`ARMADILHAS §3.1`) continuem resolvendo.

---

<!-- ID no ARMADILHAS.md monolítico: §3.1 · categoria: §3 — Ambiente (Windows, esta máquina) -->

## 3.1 `make: command not found` — RESOLVIDO em 19/08/2026

**Era:** o Bash do agente não é login shell, não lia `~/.bashrc`, e o `make` do WinGet
só estava no PATH de lá — todo comando precisava virar `bash -lc 'make ...'`.
**Resolvido:** a pasta do `make` entrou no PATH do usuário (Windows). Hoje
`command -v make` responde direto no Bash do agente, sem `-l` e sem `export PATH`.
**Se voltar a falhar:** confira se o PATH do usuário ainda contém
`...\WinGet\Packages\ezwinports.make_.../bin` — o sintoma é exatamente este título.
**Origem:** Prompt 3a (pagamentos, PR #16) · corrigido pelo mantenedor.

---

<!-- ID no ARMADILHAS.md monolítico: §3.2 · categoria: §3 — Ambiente (Windows, esta máquina) -->

## 3.2 `make contrato-check` dando "OK" falso — RESOLVIDO em 19/08/2026

**Era:** `python3` resolvia para o stub quebrado da Microsoft Store. O
`ci/freeze-de-contrato.sh` chama `python3` internamente, as duas pontas do diff falhavam
igual e "batiam" — **o portão dizia OK sem ter comparado nada**, e cada agente precisava
validar o contrato à mão.
**Resolvido em duas camadas, e a distinção importa:**

1. **A máquina:** shim `~/bin/python3` → Python 3.12 real. Isso desarmou o sintoma
   *aqui*. Não é a correção do portão: qualquer outra máquina (ou uma imagem de CI sem
   PyYAML) reproduziria o mesmo verde mentiroso.
2. **O portão:** a lógica saiu do Bash para `ci/contract_freeze.py` e passou a ser
   fail-closed por construção ([INV-CI01] em `INVARIANTES.md`). Ferramenta ausente,
   stdout vazio, contrato obrigatório ausente, congelado malformado ou raiz não
   resolvida ⇒ `ERROR` (exit 2) — nunca `PASS`. O `.sh` virou wrapper fino e procura
   `python` **antes** de `python3`, para que o shim seja conveniência local e não
   requisito arquitetural.

**Evidência de que valida de verdade (não só parou de reclamar):** com uma divergência
deliberada no `summary` de uma operação, o script imprimiu o diff e saiu com erro
(`make: *** [contrato-check] Error 1`); restaurado, voltou a `✅ OK`. Depois da
reescrita, a mesma prova foi refeita nos três estados: contrato igual ⇒ `PASS` (0),
divergente ⇒ `FAIL` (1), instrumento quebrado de propósito ⇒ `ERROR` (2).
**Ressalva histórica:** a nota original dizia *"no CI real (Linux) o script funciona de
verdade — o falso-positivo é só local"*. Isso estava **errado por sorte**. O mecanismo
nunca dependeu do sistema operacional, só de a normalização falhar nas duas pontas ao
mesmo tempo; bastava a imagem do runner não ter PyYAML para o mesmo verde aparecer no
CI. Se você encontrar essa frase em algum documento antigo, ela está incorreta.
**Se voltar a falhar:** desconfie de qualquer verde acompanhado de `command not found`.
Hoje isso é impossível por construção — `python ci/contract_freeze.py <celula>` mede e
diz em qual dos quatro estados parou.
**Origem:** Prompt 2 (catalogo, PR #15) · shim pelo mantenedor · endurecimento em Bash
no PR #21 · reescrita fail-closed no PR #22.

---

<!-- ID no ARMADILHAS.md monolítico: §5.9.1 · categoria: §5 — Portões mecânicos do CI (eles reprovam de verdade) -->

## 5.9.1 `ci/mergear.py` estoura `unknown flag: --yes` nesta máquina — RESOLVIDO 22/08/2026

**Sintoma:** `python ci/mergear.py <PR>` confere tudo verde (PASS em todos os checks),
você digita o número do PR para confirmar, e o comando interno falha:
`ERROR ao mergear: ... gh pr merge <PR> --merge --yes ... stderr: unknown flag: --yes`.
**Causa:** `gh pr merge` **nesta instalação** (`gh version 2.97.0`) não tem a flag
`--yes`/`-y` — confirmado com `gh pr merge --help`, a lista de FLAGS não a inclui.
`ci/mergear.py` (linha ~371) assume que ela existe, para evitar que o próprio `gh`
faça uma SEGUNDA pergunta de confirmação depois da que o script já fez.
**Contorno que funcionou:** chamar o `gh` direto, sem `--yes`, com stdin explicitamente
não-interativo — não trava esperando resposta, e não faz segunda pergunta:

```bash
gh pr merge <PR> --merge --delete-branch < /dev/null
```

Se o PR estiver checked out num worktree separado (comum neste repositório — RITOS.md
§1), `--delete-branch` falha só nessa etapa (`cannot delete branch ... used by
worktree`) — o merge em si já aconteceu; confira com
`gh pr view <PR> --json state,mergedBy,mergeCommit` e depois
`git worktree remove <caminho>` + `git branch -D <branch>` na sequência certa.
**RESOLVIDO em 22/08/2026** — a decisão saiu, junto com a de o merge passar ao
agente: `ci/mergear.py` não usa mais `--yes` (`comando_de_merge()` monta o comando
sem a flag; teste-guarda `test_comando_de_merge_nao_usa_yes` impede a volta), o
stdin de TODO subprocesso de portão é fechado por construção (`_nucleo.executar`,
`stdin=DEVNULL` — sem TTY o `gh` não pergunta, age; era exatamente o comportamento
do contorno acima), e a conferência `state=MERGED` ficou embutida no próprio script.
O contorno fica como registro histórico; o comando que o script imprime voltou a
ser o comando que funciona. A ressalva do `--delete-branch` com worktree continua
valendo para quem o usar à mão — o script não o usa.
**Origem:** despacho red-team, golpe 1 (PR #35), 21/08/2026; correção no despacho
governança/merge-pelo-agente, 22/08/2026.

---

<!-- ID no ARMADILHAS.md monolítico: §5.11 · categoria: §5 — Portões mecânicos do CI (eles reprovam de verdade) -->

## 5.11 Lane `traducoes` no orçamento: as muralhas aceitavam, mas `mergear.py` não conhecia a válvula — ✅ RESOLVIDO em 23/08/2026

**Sintoma (previsto, mecânico — nunca chegou a acontecer num PR real):** um lote
de tradução com a label `traducoes` e >15 arquivos, todos em
`services/*/traducoes/**`, passava verde no `orcamento-de-mudanca` das muralhas —
e na hora do merge `python ci/mergear.py <N>` reprovava com
`"N arquivos sem a label 'arquitetural'"`.
**Causa:** `checar_labels()` em `ci/mergear.py` REIMPLEMENTA o orçamento (de
propósito — confere antes do merge o que as muralhas conferiram no PR), mas só
conhecia a válvula `arquitetural`; a lane `traducoes` (PLANO-I18N.md, D9) entrou
só no `ci/orcamento-de-mudanca.sh`, porque `mergear.py` estava fora do escopo do
despacho que a criou. Duplicação de semântica entre portão e catraca = os dois
podem divergir, e divergiram aqui por um despacho de distância.
**✅ RESOLVIDO em 23/08/2026** (PR #94, despacho ci/catraca-lane, branch
`agent/ci/catraca-lane`): `checar_labels()` aprendeu a lane com a MESMA
semântica do `.sh` — `arquitetural` passa na frente (inclusive com as duas
labels juntas), a label nunca APERTA (≤15 passa com ou sem ela), e com
`traducoes` + >15 arquivos só passa se todo caminho casar
`PADRAO_DA_LANE_TRADUCOES` (`^services/[^/]+/traducoes/.+$`); um caminho fora
reprova NOMEANDO o arquivo. 13 testes-guarda novos em `ci/tests/test_mergear.py`
(198 no total, verdes), evidência vermelho→verde por patch.
**A assimetria que ficou de propósito (leia antes de "consertar"):** a catraca
confere só o CAMINHO; o MODO (executável/symlink/submódulo) segue sendo medido
só pelas muralhas. Motivo medido, não preguiça: `gh pr view --json files`
devolve apenas `{path, additions, deletions, changeType}` — **não existe campo
de modo** (sonde com `gh pr view <PR> --json files --jq '.files[0]'` antes de
supor que existe). Remedir o modo por outra via (git local, API de trees) seria
trocar uma segunda barreira barata por dependência de estado local/rede, que
ERRORa em PR legítimo. A defesa continua fechada em profundidade: `muralhas` é
check OBRIGATÓRIO e precisa estar SUCCESS para o merge sair da catraca, então
modo proibido reprova antes — e `test_lane_depende_do_modo_conferido_pelas_muralhas`
acusa se o `.sh` perder a conferência de modo em que essa decisão se apoia.
**Lição geral (vale para qualquer regra duplicada entre portão e catraca):**
duplicar semântica é aceitável aqui (a Escada da Imposição, §5.9, quer duas
barreiras), mas **toda cópia precisa de guarda mecânica contra deriva** — foi a
falta dela que abriu esta armadilha. Hoje são duas, ambas lendo o próprio `.sh`:
`test_limite_de_arquivos_bate_com_orcamento_de_mudanca` (o número) e
`test_padrao_da_lane_bate_com_orcamento_de_mudanca` (o padrão de caminho). Copiou
regra de outro portão? Escreva junto o teste que denuncia quando as duas cópias
divergirem.
**Detalhes da lane que valem para quem for mexer:** a checagem de modo usa
`git diff --raw --no-renames` (rename desdobrado em remoção+adição, para nenhum
lado escapar; dst mode `100644`/`000000` são os únicos aceitos — `100755`,
symlink `120000` e submódulo `160000` reprovam). Nos testes, o jeito de comitar
um executável de verdade no Windows é `git update-index --chmod=+x <arquivo>`
(o `core.filemode=false` ignora o bit do disco).
**Origem:** despacho ci/lane-traducoes (23/08/2026), ao ler `mergear.py` para
escrever a nota exigida pela especificação.

---
