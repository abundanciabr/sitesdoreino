# 258 — A fila não precisa de plateia: o robô esperava o pouso, e a lei já proibia

**Sintoma.** O mantenedor abre a janela e vê uma parede de "Aguardando.":
dezenas de linhas seguidas, tarefa após tarefa. A percepção dele, em
31/08/2026: *"todas as tarefas ficam com esse monte de vezes Aguardando, e
algumas demoram horas assim"*.

**Diagnóstico errado que veio primeiro (e por que ele era errado).** A primeira
resposta foi "a fila de merge está cheia porque há muitos robôs em paralelo".
Isso foi dito **sem medir**, olhando a lista de runs do `pouso.yml` e vendo
muitos "cancelled". Medindo de verdade, os 40 PRs do dia:

| o que | medido em 31/08/2026 |
|---|---|
| PR aberto até entrar (mediana) | **8,4 min** (pior do dia: 33,9 min) |
| uma passagem da pista | **34 s** (máximo 61 s) |
| passagens por hora | **326** |
| deploy chegar na VPS (mediana) | **3,2 min** |

A fila **não estava lenta**, e nada demorou horas. Os "cancelled" também não
eram falha: é o `concurrency: pouso` colapsando acordadas simultâneas numa só,
exatamente como o cabeçalho do workflow descreve. Culpar a fila era culpar o
único pedaço saudável do caminho.

**Causa real.** O robô estava **esperando o pouso** com
`ci/esperar.py --pouso`, e a lei já proibia isso desde 29/08/2026:

> "Antes de esperar, pergunte se a espera precisa existir. A melhor espera é a
> que não acontece: checks de PR não se esperam." — `RITOS.md` §2 peça 6

A frase estava no `RITOS.md` **e** no cabeçalho do próprio `ci/esperar.py`. E
mesmo assim os robôs esperavam, por um motivo simples: **`--pouso` e `--checks`
estavam listados como alvos válidos, ao lado dos legítimos.** Regra que só vive
no texto apodrece — é o padrão 2 da `RETROSPECTIVA-FASE-D.md` (garantia sem
mecanismo), aqui aplicado ao documento que criou a própria regra.

Dos ~12 min de espera por tarefa, **~8,4 min (70%) eram tempo morto do robô**
olhando uma fila que anda sozinha 326 vezes por hora.

**Solução.** Dar mecanismo à frase que já era lei:

- `ci/esperar.py`: `--pouso` **recusa** (exit 2), e a recusa ENSINA — cita o PR
  de quem a leu, mostra o `--pousar` no lugar, e traz os números acima. Escape
  consciente: `--mesmo-assim "<motivo>"`, para quem precisa depurar a própria
  pista.
- A recusa vem **antes** da linha de partida da voz: um robô que anuncia "vou
  esperar" e depois desiste ensina o oposto do que a lei quer.
- `RITOS.md` §2 peça 6 tirou `--pouso` da lista de alvos e ganhou duas regras
  de comportamento:
  **trabalhe durante o deploy** (o `Monitor` roda em segundo plano e te acorda
  — é para isso que ele existe) e **não repita cada batimento com uma linha
  sua** (o `⏳` já está na tela do mantenedor; falar quando muda o relógio, e
  não quando muda o fato, é o que constrói a parede de "Aguardando").

**O TERCEIRO erro, que quase pousou: proibir `--checks` junto.** A primeira
versão deste PR proibia `--checks` também, apoiada na letra da peça 6 ("checks
de PR não se esperam"). Isso teria tornado o rito da casa **impossível de
cumprir**: `ci/mergear.py --pousar` recusa com check em andamento (`ERROR`), e o
`CLAUDE.md` manda, no passo 1, "espere os checks concluírem" ANTES de pedir
pouso. Quem revelou foi o próprio PR #801 tentando pedir o próprio pouso, e
recebendo `RESULTADO ERROR / MOTIVO-DA-RECUSA: BASE-VELHA`.

A peça 6 fala do **laço** (atualizar → esperar → a `main` andou → repetir, as
oito voltas da `armadilhas/156`), nunca da espera ÚNICA que o portão exige. Ler
"não se espera checks" como proibição literal é confundir o laço com a espera.
**Lição de método: um portão novo precisa ser testado contra o rito que ele vai
governar, não só contra os testes que você escreveu para ele.** Os 40 testes
passavam verdes enquanto a mudança quebrava o fluxo padrão da casa.

**O detalhe que quase virou um quarto diagnóstico errado.** O `--intervalo`
do `esperar.py` é 15s e parece ser a fonte do ruído. Não é: quem controla a
fala é o `--voz` (60s), e o batimento só fura essa trava quando o *resumo
observado muda*. Em `--pouso` o resumo é estável, então a voz já respeitava os
60s. Mexer no `--intervalo` teria sido barulho contra o alvo errado — e medir
a coisa errada com precisão é como um portão morre.

**Quem faz valer:** `ci/esperar.py` (a recusa) ·
`ci/tests/test_espera.py::test_a_espera_que_nao_devia_existir_recusa_e_ensina_o_caminho`
(parametrizado pela MESMA lista que a recusa usa, para os dois nunca
divergirem) · `::test_a_recusa_nao_falou_a_partida_antes_de_desistir` ·
`::test_o_veredito_do_deploy_continua_livre` (a espera que a lei MANDA ter
nunca pode cair na recusa).

**A lição que atravessa o caso:** quando uma regra é desobedecida por robôs
que leram a regra, o defeito não está neles — está na ferramenta que deixou o
caminho errado à mão, com o mesmo peso visual do certo.
