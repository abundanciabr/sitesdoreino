# DECISÃO: a tríade de IAs, papéis fixos em vez de disputa

**Decidida pelo mantenedor em 12/09/2026.** O pedido dele, com as palavras dele:

> "ao invés de continuar a disputa para ver quem das 3 IAs pode ser a líder, a
> auxiliar e a eliminada, porque não usar outra abordagem e usar o que cada IA
> tem de melhor?"

E, na mesma tarde: "quero que você Claude seja o Maestro-Especialista com
Execução Cirúrgica desse projeto" e "altere todos os documentos do projeto
tais como CLAUDE.md dentre outros explicando o papel, trabalho,
responsabilidades e limites de cada uma das IAs da tríade".

## A lei, em uma frase

**Três IAs, três papéis fixos: Claude Code rege, Codex constrói, Antigravity
audita e verifica. O contrato entre elas é o que a casa já tinha (a fila, o
livro e os registros do conselho); nenhum formato novo nasce.**

## Por que

O conselho da Fase 4 (regulamento na pasta de trabalho do mantenedor, fora do Git) foi desenhado como
competição: cada IA propunha, as outras votavam, e o placar decidiria quem
lidera, quem ajuda e quem sai. Em 12/09/2026 ele tinha 16 fichas, 0 pontos e
0 mudanças na fábrica. A auditoria que motivou a fase (os "4 Diamantes" e o
"Ouro", do Antigravity) foi a melhor coisa que saiu dele, e ela não veio de
disputa: veio de uma IA fazendo o que faz melhor, ler o sistema inteiro.

A divisão segue a força de cada uma. Antigravity tem a maior janela de
contexto e enxerga o todo: audita. Codex tem volume, paralelismo e custo
baixo por PR em tarefa bem especificada: constrói. Claude Code segura
constituições longas, traduz achado em brief sem ambiguidade e pega o bug
sutil: rege, executa o cirúrgico e revisa o crítico.

Duas fichas do conselho foram reprovadas por um único motivo: mediram a pasta
local, que estava 82 commits atrás de `origin/main` e com o `CLAUDE.md`
mutilado. Por isso a regra 1 abaixo é a primeira.

## Os papéis

| Papel | Quem | Escreve | Nunca |
|---|---|---|---|
| Maestro | Claude Code | a decisão sobre cada achado (`voto`), a tarefa na fila com o brief roteado por `ci/economia_da_fabrica.py brief`; executa o que é cirúrgico por um despacho próprio; revisa PR crítico e publica o atestado | espera check em laço; mergeia; delega arquitetura |
| Executor | Codex | o PR pela ficha `despacho`, que grava o evento na fila e o registro no livro; a `implementacao` com prova, quando o brief a pedir | pergunta ao mantenedor; edita o clone principal; arma espera; amplia o mandato; audita; decide lei |
| Sentinela | Antigravity | achados medidos contra `origin/main` (`proposta`) e a verificação independente de cada entrega alheia (`verificacao`) | edita código ou lei; escreve despacho; grava evento ou registro; mede a pasta local |

Quem verifica o quê: a sentinela verifica toda entrega que não é de ficha
dela; a entrega de ficha da sentinela é verificada pela maestro. A revisão
independente que o portão de pouso exige antes do merge (`ci/mergear.py`,
atestado de `docs/decisoes/DECISAO-revisao-e-publicacao.md`) continua sendo
feita pelo revisor da casa e publicada pela maestro; a verificação da
sentinela vem depois do merge e mede o aceite da ficha, não o diff.

## O contrato, que já existia

Lei da casa: fato nenhum mora em dois lugares. Por isso não nascem
`despacho.json`, `resultado.json` nem `achado.json`. Os três já existem com
outro nome:

| O que a tríade chama | O que a casa já tem | Definido em |
|---|---|---|
| achado | `<AUTOR>-NNN-proposta.json`: `tipo`, `id`, `autor`, `registrado_em`, `problema`, `titulo`, `baseline` (comando e saída contra `origin/main`), `aceite`, `origem` | esta decisão |
| decisão | `<ID>-voto-claude.json`: `tipo`, `proposta`, `autor`, `registrado_em`, `proposta_sha256`, `decisao` (`aprovar`, `reprovar`, `abster`), `importancia`, `justificativa`; a tarefa criada na fila é a decisão executável | esta decisão |
| despacho | `fila/tarefas/NNN-slug.json`, cujo campo `despacho` recebe o brief compilado inteiro (`python ci/fila.py criar --despacho-arquivo <brief>`), com `modelo_recomendado`, `esforco_recomendado` e `teto_de_contexto` | `fila/LEIA-ME.md`, `CAMINHO-DOURADO.md` §2, `ci/economia_da_fabrica.py` |
| resultado | evento `submetida` em `fila/eventos/` (PR, revisão, árvore), registro em `painel/registros/`, e `<ID>-implementacao.json` (`tipo`, `proposta`, `autor`, `registrado_em`, `proposta_sha256`, `prova`, `prova_sha256`, `resultado`, `minutos_totais`, `custo_reais`, `fonte_custo`) quando o brief pedir | `fila/LEIA-ME.md`, `painel/LEIA-ME.md`, esta decisão |
| verificação | `<ID>-verificacao-<autor>.json`: `proposta`, `autor`, `registrado_em`, `implementacao_sha256`, `decisao` (`confirmar`, `recusar`, `abster`), `justificativa`, `prova`, `prova_sha256` | esta decisão |

O ciclo: a sentinela escreve a proposta; a maestro decide (voto) e, se
aprova, cria a tarefa na fila com o brief; o executor abre o PR e grava a
implementação; a pista mergeia sozinha; a sentinela verifica; o próximo
achado entra. Leitura por máquina: `python ci/fila.py listar --json`.

**Onde vivem os registros do conselho.** Na pasta de trabalho do mantenedor,
em `docs/consultorias/fase-4-otimizacao/conselho-local/registros/`, fora do
Git por orientação dele quando o conselho nasceu; se a pasta não existir, quem
escreve a cria. Os campos de cada arquivo são os desta decisão; o nome é
`<AUTOR>-NNN-<tipo>.json` (voto e verificação levam o autor no fim), com `NNN`
em sequência por autor. Quem escreve entrega o caminho do arquivo à maestro no
fecho. Publicar a pasta no repositório é decisão do mantenedor; o placar que
mora lá deixa de classificar: ele lista.

## As três regras que não se negociam

1. **Mede-se `origin/main`, nunca a pasta local.** Comando: `git fetch origin` e `git show origin/main:<caminho>` no PowerShell (no Git Bash, caminho começando por ponto quebra, `armadilhas/334`), ou uma bancada de leitura com `git worktree add ../wt-leitura --detach origin/main`.
2. **Ninguém espera em laço.** Depois de `make pr`, o executor encerra; a maestro publica o atestado, pede pouso com `python ci/mergear.py <N> --pousar` e encerra. A pista acorda por evento e mergeia. `python ci/esperar.py --entrega <N>` é consulta única, em JSON.
3. **Piso de segurança.** Nenhum despacho remove guarda de CI nem lei do `CLAUDE.md`. Lei muda com decisão escrita em `docs/decisoes/`.

## O que a tríade não muda

- A lei do lote: pedido colado direto numa sessão continua sendo lote regido por aquela sessão, seja ela Claude Code ou Codex, com as fichas de `.claude/agents/` ou `.codex/agents/`.
- O rito do PR: bancada por `ci/sessao.py`, `make pr` com recibo e eventos a bordo, revisor independente, atestado, pouso pela pista.
- Tarefa que o executor descobre no caminho ele registra na fila (`RITOS.md` §5) e devolve à maestro, que decide se entra no lote.
- Pedido colado no Antigravity vira proposta medida contra `origin/main`, devolvida à maestro; ele não executa.

## O primeiro lote, em 12/09/2026

| # | Despacho | Ficha | Dono | Estado |
|---|---|---|---|---|
| 1 | Trava contra apagamento silencioso de lei | ANTIGRAVITY-004 | Codex | TAR-371, criada pelo PR #1604 |
| 2 | O merge fecha a tarefa | CLAUDE-010, absorve CLAUDE-002 | sessão remota, autorizada pelo mantenedor com desenho diferente da ficha: a conclusão viaja dentro da própria entrega | PR #1603, atestado e pouso pedidos pela maestro |
| 2b | Reconciliar as 28 tarefas já mergeadas e presas em "em execução" | recomendação da sessão do PR #1603 | a decidir pelo mantenedor | por criar |
| 2c | Aposentar a sombra de conclusão em `ci/mergear.py` | recomendação da sessão do PR #1603 | Claude Code | por criar |
| 3 | Ficha do despacho com `tools:` fechado e `make pr` que imprime o fecho | CLAUDE-011 (a) e (b) | Claude Code | por criar |
| 4 | Semear os índices de armadilha na abertura da bancada | CLAUDE-005 | Codex | por criar |
| 5 | Muralha da espera enxergar o ramo Monitor | CLAUDE-001 | Codex | por criar |
| 6 | Trava de edição do clone principal, cobrindo escrita por shell | CLAUDE-008 | Codex | por criar |
| 7 | Folga no teto do `CLAUDE.md`, movendo história para `docs/decisoes/` | CLAUDE-003 | Codex | por criar, depende de 1 |
| 8 | Tirar as três coisas que dizem fazer o que não fazem | CLAUDE-006 | Codex | por criar |
| 9 | Medir o ciclo inteiro de uma tarefa cobaia | CLAUDE-007 | Antigravity | por criar, depende de 1 a 8 |

Já feito antes do lote, medido em `origin/main` = `22a9bd26`: ganchos por
comando 5 para 0; `CLAUDE.md` de 20.515 para 11.893 bytes com as 13 leis;
saída de teste de 18.555 para 159 bytes (`ci/resumo_de_teste.py`); mutação
automática (`ci/provar_guardas.py`); microcommits abolidos; pista por evento.

Adiados: CLAUDE-009 (pegar-lote) até o despacho 2b mostrar lote máximo maior
que 1; CLAUDE-011 (c) até (a) e (b) medirem; ANTIGRAVITY-005 até o despacho 2
provar se basta. Reprovadas: ANTIGRAVITY-001 e 003, substituídas pela 004
pela própria autora; ANTIGRAVITY-002, porque a pista já acorda por evento.

## Quem faz valer

`ci/pr.py` (recibo e eventos a bordo, tarefa vinculada), `ci/fila.py`
(balcão, `validar` fail-closed na muralha), `ci/mergear.py` (atestado
independente e pouso pela pista) e os testes das fichas
(`ci/tests/test_fichas_de_robo.py`, `ci/tests/test_codex_nativo.py`). A
divisão de papéis em si é julgamento: nenhum portão sabe qual IA está
digitando. O que ele sabe conferir é o rastro: tarefa na fila, brief roteado,
PR com recibo, atestado com três identidades distintas.

## A memória

- 12/09/2026, manhã: conselho local da Fase 4 (Codex propõe o regulamento; Claude Code e Antigravity escrevem fichas; 0 pontos).
- 12/09/2026, tarde: o mantenedor pede a tríade. Claude Code escreve o protocolo e os dois convites na pasta de trabalho do mantenedor, fora do Git. Codex aceita às 16:49, Antigravity às 16:47; os aceites ficam gravados na mesma pasta. O protocolo é esta decisão.
- 12/09/2026, noite: PR #1603 (despacho 2) recebe atestado e pedido de pouso; PR #1604 cria a TAR-371 (despacho 1) e a TAR-370; esta decisão entra na lei.
