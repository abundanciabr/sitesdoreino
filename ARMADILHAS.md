# ARMADILHAS — o que já custou tempo neste repositório

> Documento **vivo**, e desde 23/08/2026 **particionado**: o monólito de 1.490
> linhas (48% da carga de contexto de todo despacho — PLANO-10X, Alavanca 2) virou
> **uma entrada por arquivo** em `armadilhas/`, com um índice gerado. Cada entrada
> é tempo que um agente já perdeu — e que o próximo não precisa perder.

**Existe para uma coisa só: impedir que o mesmo problema seja resolvido do zero em
toda tarefa.** Cada redescoberta custa tokens, custa rodadas de teste e atrasa o
despacho. Se você gastou mais de dois minutos entendendo algo que não era a sua
tarefa, isso pertence aqui.

## Como usar (agente) — a regra nova, em uma frase

**Use o contexto direcionado da abertura por caminho e sintoma e abra as origens.**
As regras globais, as dos caminhos e os oito padrões da Retrospectiva continuam obrigatórios.

Agente, aqui, é quem constrói pela ficha de despacho: o sub-agente `despacho` ou o
Codex, o executor da tríade (docs/decisoes/DECISAO-triade-de-ias.md). Antigravity, a
sentinela, só lê: audita e verifica, não cria entrada nem despacho. Claude Code, como
maestro, escreve o brief e julga as lições que as entradas trazem.

1. **Antes de codar:** siga o §2 abaixo, confira o contexto emitido, suas origens,
   ausências e truncamento; abra as entradas do brief e as recuperadas.
2. **Quando bater de frente com algo:** refine `--caminho`/`--sintoma` em
   `ci/sessao.py --contexto`, amplie `--limite-contexto` ou, para aprofundamento,
   consulte `armadilhas/INDICE.md`. As entradas começam pelo sintoma concreto.
3. **Ao terminar o despacho — isto não é opcional:** crie **um arquivo novo**,
   `armadilhas/NNN-slug.md`, no formato
   `Sintoma → Causa → Solução → Origem`, e rode
   `python ci/indice_de_armadilhas.py` (ou `make indice`) para regenerar o índice.
   **O `NNN` se PEDE, não se escolhe** — `python ci/reservar.py numero armadilha`
   devolve o próximo, reservando-o no servidor do GitHub (comparar-e-trocar, a
   mesma trava do livro). "Próximo número livre" lido da pasta não tem trava
   nenhuma: duas sessões leem, veem o mesmo livre, e o `git merge` junta os dois
   arquivos sem ter o que reclamar — nomes e hunks diferentes. Medido em
   29/08/2026: uma entrada colidiu DUAS vezes seguidas no mesmo PR
   (`armadilhas/189`). **Isto deixou de ser conselho em 29/08/2026:**
   `ci/muralha-das-reservas.sh` reprova, em todo PR, número de armadilha que
   apareça pela primeira vez sem ter sido pedido — e a recusa já traz o
   conserto. Só o que é NOVO em relação à base é cobrado: o catálogo histórico
   e o renomear-slug de entrada antiga passam.
   **Nunca acrescente ao fim deste arquivo, e nunca edite a entrada de outro
   agente para encaixar a sua** — arquivo novo por entrada é exatamente o que faz
   duas sessões paralelas pararem de colidir no mesmo hunk. Entrada sem sintoma
   concreto não ajuda ninguém: descreva o erro real, não a lição abstrata.
4. **Se a solução definitiva não estiver nas suas mãos** — depende de instalar algo
   na máquina, de uma conta paga, de uma permissão, de uma decisão de arquitetura —
   **registre na tabela §1 do `ARMADILHAS-OPERACAO.md` E avise o humano no seu
   relatório final, em texto claro.** Você contorna hoje para não travar; ele
   resolve de vez quando puder. Contornar em silêncio é o que faz o mesmo atrito
   voltar no próximo despacho, e no seguinte.

## Onde cada coisa mora (para não duplicar)

| Documento | Público | Guarda |
|---|---|---|
| `CONSTITUICAO.md` + `constituicoes/` | agentes | o que é **proibido** |
| `CAMINHO-DOURADO.md` | agentes | como fazer **certo** (receitas) |
| `INVARIANTES.md` | agentes | o que **não pode quebrar** |
| **`armadilhas/INDICE.md`** | **quem precisar de aprofundamento** | o mapa do que a **realidade cobrou** — uma linha por armadilha |
| **`armadilhas/NNN-slug.md`** | o agente que o índice mandar abrir | a armadilha em si (sintoma → causa → solução → origem) |
| **`ARMADILHAS.md`** (este) | todo agente | a regra de uso acima + a partida rápida (§2) |
| `ARMADILHAS-OPERACAO.md` | **maestro (Claude Code), sentinela (Antigravity), o humano** | §1 precisa-de-você · como se mergeia · painéis · §9 dívidas abertas |
| `docs/historico/RESOLVIDAS.md` | quem precisar do histórico | armadilhas já resolvidas — fora da dieta do despacho |
| `services/<celula>/LICOES.md` | agente **daquela** célula | decisões e armadilhas **só** daquela célula |
| **`painel/registros/NNN.js`** | **o humano** (via `painel/painel.html`) | o que ACONTECEU — um registro por acontecimento, só se acrescenta |

Regra de bolso: **se serve para qualquer célula, é uma entrada em `armadilhas/`. Se
só faz sentido dentro de uma célula, é no `LICOES.md` dela. Se só o humano resolve,
é o `ARMADILHAS-OPERACAO.md`. Se é um FATO do projeto (entreguei, quebrou, decidi,
preciso de você), é um registro em `painel/registros/`.**

> **Por que tudo isto é versionado, painel incluído (mudou em 26/08/2026):** um
> agente trabalha dentro de um `git worktree`, e worktree só contém arquivo
> rastreado. Até 25/08 os painéis viviam em `arquivos/` (gitignored) e o agente não
> os enxergava — o que também significava que **nenhuma trava alcançava os dados**, e
> foi assim que o painel-10X pôde apodrecer em silêncio. Desde a reforma, o livro de
> ocorrências mora em `painel/registros/`, **dentro do Git**: existe no seu worktree,
> viaja no seu PR, e a `muralha-do-painel` o valida em todo PR. O que ficou em
> `arquivos/` são lápides e não se edita.

---

## §2 — Partida rápida (os 6 primeiros minutos de qualquer sessão)

```bash
make sessao CELULA=<celula> TAREFA=<slug>
# Sem make: python ci/sessao.py --celula <celula> --tarefa <slug>
```

O RITOS §1 é a entrada canônica: cria ou retoma a bancada, prepara os serviços
exigidos pela célula, mede o baseline e emite contexto. Confira o log e a
Declaração antes de editar; não repita a preparação manual.
Área sem serviço usa `SEM_CONTAINER=1` ou `--sem-container`; nesse caso o
baseline fica não medido e você roda os testes dos alvos antes de editar.
FAIL herdado: pare e reporte. ERROR de Docker, dependências ou conexão: corrija
o ambiente informado pela abertura e repita a mesma entrada, preservando a bancada.

**Antecedente histórico (25/08/2026):** a leitura literal de "pare e reporte"
quase abortou oito despachos por Redis ausente na antiga receita manual.
`armadilhas/119` conserva o caso; a abertura agora prepara os instrumentos.

**Planeje a divisão ANTES de escrever código.** O orçamento de 15 arquivos é portão
mecânico (§5.1). Uma célula nova com modelo + migrations + clientes + middleware +
guardas de invariante **não cabe** em 15 arquivos junto com páginas. Conte os arquivos
no papel antes da primeira linha; se estourar, divida o despacho em dois PRs e diga
isso na primeira resposta, não no fim.

---
