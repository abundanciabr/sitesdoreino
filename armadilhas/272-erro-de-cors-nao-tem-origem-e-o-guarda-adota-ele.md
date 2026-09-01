---
schema_version: 2
armadilha: 272
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: e2e/painel_no_navegador.js
sinal:
  - `blocked by CORS policy`
  - `O painel NÃO cumpre o orçamento de amplificação`
---

# O check `painel-no-navegador` reprovou um PR sem defeito, e o rerun ficou verde sem uma linha de diferença: o erro de CORS chega SEM origem, e quem classifica pela origem o adota como seu

**Sintoma.** O check `painel-no-navegador` falha com

```
  FAIL http · 10: ZERO erro de console (da NOSSA página)  → Access to fetch at
  'https://api.github.com/…' from origin '…' has been blocked by CORS policy: …
❌ 1 caso(s) FALHARAM no navegador.
   O painel NÃO cumpre o orçamento de amplificação.
```

num PR que não toca `painel/` nem `e2e/`. `gh run rerun <id> --failed`, sem
mudar uma vírgula, fica verde. Aconteceu em 01/09/2026.

**Causa.** O corte "nosso × externo" de 29/08/2026 (a cura do 403 do GitHub,
contada por inteiro no comentário de `erroDaNossaPagina`) classifica o erro de
console pela **origem** da mensagem, e fecha o resto com `if (!origem) return true` — na dúvida, o dono é nosso. A
regra é a certa, mas ela tinha um ponto cego de fato: **o navegador reporta o
erro de CORS sem url de origem**. O único lugar onde o alvo do pedido aparece é
o TEXTO, que a função não olhava. Resultado: o erro mais claramente de terceiro
que existe caía justamente no ramo reservado a "não sei de quem é isto".

O painel foi desenhado para sobreviver a essa falha (ele pinta "não consegui
perguntar ao GitHub"), então o que o guarda chamava de defeito era um estado
esperado. É a mesma doença de 29/08, com outra porta de entrada: FAIL contra
ERROR (`RETROSPECTIVA-FASE-D` §1) — "o painel está quebrado" e "não consegui
medir o painel porque a rede lá fora falhou" são fatos diferentes. E o preço é
alto porque nesta casa o pouso depende de todo check verde (`ci/mergear.py`):
guarda que pisca custa a etiqueta de pouso de um PR são, e ensina a ignorar
vermelho.

**Solução — e a mina que ela precisa desviar.** Sem origem declarada, passe a
ler o texto. Mas **não por substring**, que é a correção que salta aos olhos:
`DESTINOS_EXTERNOS` inclui `meshcraft.top`, que é o site **da casa**, e o painel
tem links para ele na tela. "O texto cita um endereço da lista ⇒ é de terceiro"
faria um `TypeError` nosso que por acaso mencionasse esse endereço perder o
poder de reprovar. Trocaríamos um guarda que pisca por um guarda que dorme, e o
segundo é o pior dos dois: barulho errado se percebe, silêncio errado não.

O que ficou em `e2e/painel_no_navegador.js`:

1. **Com origem declarada, é ela quem decide** e o texto nem é olhado. Tendo o
   fato melhor, não se recorre ao pior.
2. **Sem origem, o texto só isenta se for um RELATO do navegador sobre pedido
   barrado** (`RELATOS_DE_PEDIDO_BARRADO`, lista fechada de formas, cada uma com
   o alvo em posição conhecida) **e** se o alvo lido de dentro da mensagem
   estiver em `DESTINOS_EXTERNOS`. Não é "o texto menciona": é "o pedido que
   falhou era para". Menção nunca vira isenção.
3. **Todo o resto continua caindo no `return true`.** O fail-closed é a regra
   certa; o defeito nunca foi ele, foi a falta de um fato antes dele.

**A régua que generaliza, e é o que vale levar daqui:** ao afrouxar um guarda
para parar de reprovar terceiro, pergunte **qual identificador você vai usar** e
se ele pertence só ao terceiro. Um endereço que também é seu (o próprio domínio,
`localhost`, o nome da empresa) não distingue nada, e a mesma linha que cala o
alarme falso cala o verdadeiro. A isenção tem de nascer de um fato **estrutural**
da mensagem (o campo, a posição, a forma), nunca de uma palavra achada nela.

**Como isto se prova.** `provaDoCorteExterno()` no mesmo arquivo, que roda no
começo do rito, antes de qualquer medição: o que está sob teste é a
classificação, não a rede. Os quatro casos novos e as três
mutações que os validaram, cada vermelho nomeando o caso que caiu
(`armadilhas/268`):

| desfazer | o caso que fica vermelho |
|---|---|
| o conserto do CORS | `corte CORS: pedido barrado à api.github.com NÃO reprova o painel` |
| a proteção da mina (substring) | `corte CORS: erro NOSSO que só MENCIONA meshcraft.top continua reprovando` |
| a conferência do alvo | `…cuja vítima é a NOSSA página…` e `…a destino NÃO declarado reprova` |

**Origem.** 01/09/2026, TAR-101 (PR #839), a partir de um falso vermelho medido
num PR do lote do dia. Irmã da cura de 29/08/2026, que nunca virou entrada no
catálogo e vive só no comentário do arquivo: esta é a metade que escapou dela.
