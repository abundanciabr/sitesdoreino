---
schema_version: 2
armadilha: 537
estado: documentada
degrau: 5
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: saber se um alerta aberto já foi resolvido exige conferir a fonte (PR, fila, deploy, site) um por um; nenhum teste fixo decide isso sem julgar o livro inteiro a cada PR.
sinal:
  - `o resumo pesa \d+ bytes e o orçamento é \d+`
gatilho:
  - ci/encerramento_alertas.py
licao: "Resumo no teto: meça por porta; nao-comprovado já tem teto de 12 e baixa não o esvazia. A alavanca é problemasAbertos: audite cada alerta na fonte e escreva uma baixa verde com responde_a. Recibo âmbar de PR integrado pede baixa de quem integra."
---

# 537: resumo do painel no teto; a alavanca é dar baixa nos alertas já resolvidos, e `nao-comprovado` deixou de ser alavanca

**Data:** 27/09/2026 · **Onde:** `painel/logica.js::montarResumo`, `python ci/pr.py` de qualquer sessão · **Custo evitado:**
subir `ORCAMENTO_RESUMO_BYTES` sem decisão do mantenedor, ou auditar `nao-comprovado` sem ganho nenhum, enquanto o build de todas as sessões segue reprovando

## Sintoma

```
❌ ... o resumo pesa 154001 bytes e o orçamento é 153600 — veja O QUE está se
acumulando na capa antes de pensar no teto.
```

`node painel/gerar_manifesto.js` reprovou dentro de `python ci/pr.py` numa
frente sem relação com o painel; o PR 2208 reprovou em muralhas pelo mesmo
motivo (154010 bytes, run 36315793510). Sem registro novo nenhum, o resumo
já estava em 153.208 de 153.600 (folga de 392): qualquer recibo âmbar ou
vermelho de qualquer sessão derrubava o build.

## Causa

A `armadilhas/317` (04/09) apontou dois motores sem teto, `nao-comprovado` e
`problemas`. Metade disso envelheceu:

- `nao-comprovado` ganhou `SEM_PROVA_NO_RESUMO = 12`: são 12 itens no resumo,
  qualquer que seja o tamanho do livro (12 de 80 em 27/09, 6.762 bytes). E
  nenhuma baixa o esvazia: o filtro `naoComprovados` lê `evidencia` e
  `verificado_em` do PRÓPRIO registro, e registro não se edita.
- `problemasAbertos` (âmbar ou vermelho sem `responde_a`) continua sem teto de
  contagem: 87 itens, 72.862 bytes, 47,6% do resumo. Uma baixa com
  `responde_a` tira o alerta dessa lista (`respondidos`), e é por isso que ela
  é a alavanca.

Por que acumulou: 66 dos 87 já estavam resolvidos e nunca ganharam baixa.
26 eram recibos âmbar do `ci/pr.py` ("Revisão, integração e publicação não
verificadas") cujo PR integrou depois; 27 eram incidentes consertados por
outro PR; o resto, notas, medições e uma decisão já respondida por mandato.
`painel/LEIA-ME.md` já manda escrever a baixa ao confirmar o resultado; na
prática, quase ninguém volta ao recibo depois do merge.

## Solução

1. Meça o peso por porta com a mesma lógica de `montarResumo`
   (`problemasAbertos`, `caixaDeEntrada`, `naoComprovados`, recentes, mapa)
   antes de pensar em teto.
2. Se `problemasAbertos` domina, audite cada alerta contra a fonte:
   `gh pr view <N> --json state,mergeCommit`, evento `concluida` na fila, run de
   deploy, `curl` do endereço citado. Sem prova, o alerta fica aberto.
3. Para cada alerta provado resolvido, escreva um registro NOVO: tipo `nota`,
   `relacao: "baixa"`, `gravidade: "verde"`, `responde_a` com o id exato,
   `verificado_em` de hoje e `evidencia` com a URL completa do PR que o alerta
   cita. `ci/encerramento_alertas.py` recusa baixa de entrega sem essa URL, e
   recusa verde que cite PR de outra entrega em alerta sem baixa no mesmo PR.
4. Pedido ao dono (`precisa_do_dono: true`) só ganha baixa quando a ação
   pedida está provada (o mandato transcrito, o PR que ele liberou integrado).
5. Não suba `ORCAMENTO_RESUMO_BYTES`: é decisão do mantenedor.
6. Prevenção: quem vê integrado um PR cujo recibo nasceu âmbar escreve a baixa
   no mesmo dia.

Custo da baixa no resumo: quase zero. Registros do mesmo dia só têm data, e no
empate a janela dos 30 recentes fica com os primeiros do dia; baixa escrita
depois deles não entra no resumo (o empate virou tarefa própria na fila).

## Evidência

Auditoria de 27/09/2026 na bancada `agent/painel/baixa-dos-problemas-abertos`:
87 alertas conferidos contra GitHub, fila e site, 66 com baixa, 21 abertos
por falta de prova. Parente de `armadilhas/317`.
