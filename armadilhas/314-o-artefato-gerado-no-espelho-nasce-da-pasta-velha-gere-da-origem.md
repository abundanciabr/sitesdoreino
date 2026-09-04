---
schema_version: 2
armadilha: 314
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/tests/test_indice_com_a_origem.py
---

# O artefato gerado no espelho nasce da PASTA VELHA, e o conserto que já entrou na `main` não vale em sessão nenhuma: gere da origem, não do disco

**Sintoma.** Nada dá erro. O sino toca em cima de uma linha de sucesso com uma
assinatura que a `main` consertou dias atrás; ou fica mudo numa falha cuja
armadilha entrou no catálogo ontem. Medido:

```
30/08/2026  espelho 378 commits atrás → SINAIS.json com 7 assinaturas (a main tinha 45),
            ainda com `d[íi]vida do livro` sem âncora (a versão PRÉ-conserto da 185)
04/09/2026  espelho 195 commits atrás → 151 assinaturas (a main tinha 168), 12 entradas a menos
```

**Causa (estrutural, irmã da `148` e da `234`).** Os hooks de
`.claude/settings.json` rodam `python "${CLAUDE_PROJECT_DIR}/ci/…"`, e
`CLAUDE_PROJECT_DIR` é o clone PRINCIPAL, o espelho que a `armadilhas/135`
proibiu de ser bancada. `SINAIS.json`, `INDICE.md` e `GUARDAS.json` são
gerados (TAR-022) e nascem no `SessionStart` **dos `armadilhas/*.md` daquela
pasta**. O espelho não anda a cada merge; a pasta dele é a do dia em que alguém
o atualizou pela última vez. A `148` é o agente lendo do espelho por vontade
própria; a `234` é o agente recebendo ORDENS velhas; esta é a MÁQUINA que julga
lendo dados velhos, e máquina não lê aviso.

**Solução (TAR-050): a fonte do gerador no principal é a UNIÃO com `origin/main`.**
`ci/indice_de_armadilhas.py --tambem-aqui` (o modo do `SessionStart`) detecta
que a árvore é o principal (`.git` é diretório) e coleta as entradas de
`origin/main` pelo cache do git (`git ls-tree` + um `git cat-file --batch`, sem
rede, um processo só), unindo com a pasta local, **a pasta vencendo pelo
número** (quem escreve uma entrada nova a tem só na pasta). Numa bancada
(worktree) nada muda: ela nasceu de `origin/main` e a entrada nova está nela.
`make indice`, o pre-commit e a muralha do CI chamam sem flag: nada muda para
eles. O `INDICE.md` gerado assim diz no topo quantas entradas ainda não
existem naquela pasta e como abri-las (`git show origin/main:armadilhas/…`).

As três coisas que a comparação dos caminhos decidiu, para não reabrir:

| caminho | por que não |
|---|---|
| 2. recusar-se a rodar com artefato velho | transfere o trabalho para quem está na frente; e o hook roda em TODA sessão, então "recusar" vira barulho diário (`armadilhas/174`) |
| 3. manter o espelho fresco | não é tarefa de robô: a pasta é compartilhada e pode ter trabalho não commitado (`135`); virou pedido ao mantenedor no livro |
| 1. gerar da origem (escolhido) | cura os DADOS para sempre depois de um refresh; sem rede; sem tocar no espelho; a entrada nova continua sendo vista (união, local vence) |

**O que isto NÃO cura, e é o centro da lição:** o CÓDIGO dos hooks (este
gerador, o sino, as muralhas) também é o do espelho. Um conserto em `ci/` só
passa a valer em cada máquina depois do PRÓXIMO refresh do espelho. A diferença
que faz este caminho valer a pena: os DADOS (assinaturas) mudam todo dia, e
depois de um refresh ficam frescos para sempre; o código muda raramente. Quando
você consertar um hook e o hook da sua própria sessão continuar errado, não é o
conserto: é o espelho (a `312` registra esse engano com o sino).

**Como provar sem rede (`armadilhas/195`):** um `origin` bare em `tmp_path`, um
clone que faz `git fetch` mas não move o HEAD (o estado exato do espelho), uma
segunda "sessão" empurrando a entrada 002, e uma 003 só na pasta. Antes: 2
assinaturas. Depois: 3, com a 003 intacta. Mutações que derrubam a suíte:
`unir` ignorando a origem (4 failed), `e_o_principal` sempre False (2),
origem passando por cima da pasta (2).

**Origem.** TAR-050, 04/09/2026 (lote `ci` de 03/09), medida da TAR-043/045
(30/08/2026, registros `20260830-086` e `-093`). Guarda:
`ci/tests/test_indice_com_a_origem.py`.
