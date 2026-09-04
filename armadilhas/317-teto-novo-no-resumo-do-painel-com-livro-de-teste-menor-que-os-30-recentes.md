---
schema_version: 2
armadilha: 317
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  dono: painel/testes/teste_logica.js
sinal:
  - `o resumo pesa \d+ bytes e o orçamento`
  - teto de texto novo em `painel/logica.js`
  - mutação de guarda do painel passou verde
  - `RECENTES_NO_RESUMO`
  - `CAIXA_COM_DETALHE`
  - `PROBLEMAS_COM_DETALHE`
---

# Teto de texto novo no resumo do painel: com um livro de teste menor que os 30 recentes, a mutação que apaga a porta certa passa VERDE

**Sintoma.** O resumo do painel encosta no orçamento (`o resumo pesa 153780 bytes
e o orçamento é 153600`) e a cura é a que a casa já usou uma vez: um teto de
TEXTO num bloco que só cresce, no molde do `PROBLEMAS_COM_DETALHE` de
02/09/2026. Você escreve o guarda no molde certo, os quatro casos passam, e o
guarda parece bom. Aí você faz a mutação deliberada que a lei manda
(`armadilhas/264` a `272`) e uma delas **passa verde**: apagar a linha
`marcar(apenasTitulo, blocos.caixa)`, que é justamente a linha sem a qual o
registro cortado **desaparece do resumo inteiro**, não perde apenas o parágrafo.

Foi o caso real do TAR-119, em 04/09/2026: o livro sintético do teste tinha 24
registros.

**Causa.** `montarResumo` tem SETE portas para o resumo, e uma delas é
`RECENTES_NO_RESUMO = 30` (os 30 registros mais recentes entram sempre, ao
menos como título). **Num livro de teste com menos de 30 registros, TODO
registro entra por essa porta** — inclusive os que a sua porta nova deveria
carregar. O guarda mede o teto de texto corretamente e não consegue medir a
perda de FATO, porque no cenário dele nenhum fato pode se perder. É a mesma
doença do cenário fraco que já fez a guarda de soma mentir no painel de gestão
da Caixa: o teste está certo, o mundo dele é que é pequeno demais para conter o
erro.

**Solução.** O livro do teste tem de ser **maior que `RECENTES_NO_RESUMO`**, com
os registros da regra nova FORA da janela dos recentes:

- os registros que a regra nova governa vão para um mês ANTIGO;
- em cima deles, **30 ou mais** registros de enchimento, mais novos, que ocupam
  a janela inteira dos recentes;
- pelo menos um dos registros governados com `frente: null`, para não haver
  segunda porta pelo `esperando` do Meu mapa.

Com isso, a porta nova é a única porta daqueles registros, e a mutação que a
apaga fica vermelha na hora. Depois de trocar 12 registros de enchimento por
30, as seis mutações do TAR-119 foram pegas.

**A régua para a próxima porta:** antes de acreditar num guarda de recorte do
painel, pergunte **por quantas portas cada registro do seu cenário chega ao
resumo**. Se a resposta for mais de uma, o guarda mede a porta errada.

## Duas coisas medidas no mesmo dia, para o próximo não remedir

**1. Idade não pode ser régua do resumo.** O pedido natural, e o que estava
escrito no despacho do TAR-119, é *"pendência com mais de N dias viaja só como
título"*. Isso **cruza a linha que o `gerar_manifesto.js` declara em letras
grandes**: só entra no resumo o que NÃO depende do relógio. O resumo é montado
uma vez, no build, e lido por meses; congelar "tem mais de N dias" ali
fossilizaria exatamente o frescor que o painel existe para ter. A tradução
certa é uma **contagem**: os N mais recentes ficam com o texto. A ordem por data
dá o mesmo resultado com qualquer relógio; a idade, não.

**2. Onde o peso do resumo realmente está** (medido em 04/09/2026, livro de 677
registros, resumo de 137,1 KB antes do corte). Atribuição EXCLUSIVA, ou seja,
registros que só chegam ao resumo por aquela porta:

| porta | exclusivos | bytes |
|---|---|---|
| `nao-comprovado` | 46 | 28,5 KB |
| `problemas` (abertos) | 19 | 35,4 KB |
| `recentes(30)` | 14 | 10,4 KB |
| `vence_em_dias` | 9 | 10,5 KB |
| `mapa` | 7 | 8,4 KB |
| `caixa` | **0** | 0 |

A caixa "Precisa de você" tem **zero** exclusivos, porque todo pedido também
aparece no `esperando` do Meu mapa (quando tem frente). O que ela custava era
TEXTO: 10 pedidos abertos, 22,4 KB, a única fonte de texto completo sem teto
nenhum. Cortá-la levou o resumo de 91,4% para 87,7% do orçamento.

**Os dois motores que continuam sem teto são `nao-comprovado` e `problemas`, e
eles crescem em CONTAGEM, não em texto** (cerca de 700 bytes por item, para
sempre): uma entrega sem prova conferida e um incidente aberto nunca saem
sozinhos. Neles o corte de texto já foi feito e não há mais o que cortar sem
cortar fato, porque o cabeçalho do bloco conta os itens que chegam. Quando o
orçamento apertar de novo, **a resposta não é subir o teto** (que é desenho,
`painel/LEIA-ME.md`, "o tanque à vista"): é olhar por que 46 entregas estão sem
prova conferida e 21 incidentes seguem abertos.

**Origem.** TAR-119, 04/09/2026, PR do teto de texto da caixa "Precisa de você"
em `painel/logica.js`. Parente de `armadilhas/264` a `272` (a mutação deliberada
é o que separa guarda de decoração) e do padrão 1 da
`docs/decisoes/RETROSPECTIVA-FASE-D.md` (falso-verde).
