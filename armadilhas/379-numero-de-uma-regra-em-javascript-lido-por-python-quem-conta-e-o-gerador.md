---
schema_version: 2
armadilha: 379
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  dono: services/admin/tests/test_central_de_pendencias.py
gatilho:
  - services/admin/apps/core/pendencias.py
sinal:
  - `precisa_do_dono` em código Python
  - `caixaDeEntrada`
licao: regra que mora em painel/logica.js NAO se reescreve em Python — a imagem da admin nao tem Node, entao quem conta e o GERADOR (no deploy) e a celula so le o numero carimbado em painel.html. Reescrever ja custou uma divergencia medida (Python 6, painel 7).
---

# A regra mora em JavaScript, a tela precisa dela em Python, e o caminho não é reescrever

**Sintoma:** você precisa mostrar, numa tela Django, um número que já é
calculado por `painel/logica.js`. Por exemplo *"quantas decisões estão paradas
esperando o mantenedor"*, que é `precisa_do_dono: true` sem um registro que
responda. O caminho óbvio tem quatro linhas de Python, lê `painel/registros/` e
funciona na primeira tentativa. Todo teste fica verde.

Meses depois, a tela e o painel mostram números diferentes para a mesma
pergunta, e ninguém sabe qual está certo.

**Isso já aconteceu aqui, medido em 29/08/2026:** `ci/metricas_da_fabrica.py`
procurava o texto `precisa_do_dono: true` dentro do arquivo. Registro gravado com
as chaves entre aspas (`"precisa_do_dono": true`, forma que o livro aceita sem
reclamar) não casava, e o pedido simplesmente não era contado. **O Python dizia
6 e o painel dizia 7.** A cura foi o Python parar de contar e passar a chamar
`node -e` sobre a mesma função do painel.

**Causa:** a lei anti-duplicação do `CLAUDE.md` fala de FATOS, e quem lê rápido
conclui que uma REGRA reescrita em outra linguagem não é duplicação, porque
"não é um dado, é lógica". É pior: um fato duplicado diverge quando alguém edita
um dos dois; uma regra duplicada diverge sozinha, no primeiro caso de borda que
as duas implementações tratam diferente, e ninguém edita nada.

**E a saída de 29/08 não serve para uma célula:** `ci/metricas_da_fabrica.py`
roda no PC de quem desenvolve e no runner do CI, onde há Node. A imagem da
`admin` é `python:3.12-slim`, e não tem Node nem vai ter. Chamar `node -e` de
dentro de uma view seria um 500 em produção com a suíte inteira verde, que é a
família da `armadilhas/097`.

**Solução: quem conta é o GERADOR, no deploy, e a célula só lê.**

O `deploy-celula` já roda `node painel/gerar_manifesto.js` antes de embutir a
pasta na imagem (passo "Embutir o painel do dono"). Então o gerador chama a
função de verdade e carimba o resultado na página, em forma rígida e numa linha
só:

```js
// painel/gerar_manifesto.js
var pedidosDoDono = LOGICA.caixaDeEntrada(registros, new Date("2000-01-01T12:00:00"));
...
"  pedidosDoDono: { quantidade: " + pedidosDoDono.length + ", maisAntigoQuando: " +
  JSON.stringify(pedidosDoDono.length ? pedidosDoDono[0].registro.quando : null) + " },",
```

e a célula lê com um padrão, sem executar JavaScript nenhum:

```python
# services/admin/apps/core/pendencias.py
_CARIMBO_DA_FILA = re.compile(
    r'pedidosDoDono: \{ quantidade: (\d+), maisAntigoQuando: (null|"[^"]*") \}'
)
```

**A sentinela de data não é descuido.** `caixaDeEntrada` recebe um instante, e o
bloco de dados do painel proíbe carimbar qualquer coisa que dependa do relógio
(idade em dias é contada no navegador de quem abre, para não fossilizar o
frescor). Isto pode viajar embutido porque o FILTRO dela não olha data nenhuma,
e a ORDEM é por `aguardandoDias` decrescente — que, para qualquer instante fixo,
é a mesma ordem de `quando` crescente. O que viaja é a contagem e a data do mais
antigo, as duas independentes do relógio.

**Os dois guardas, e por que precisam ser dois:**

1. `painel/testes/teste_gerador.js` prova que o carimbo é a fila DE VERDADE, e
   não um contador de campos: um livro com dois pedidos e uma resposta tem de
   carimbar 1, não 2. Sem esse caso, um gerador que carimbasse `quantidade: 0`
   para sempre passaria, e a tela diria "nada esperando você" com a caixa dele
   cheia.
2. `test_o_carimbo_da_fila_casa_com_a_pagina_REAL_do_gerador`, do lado Python,
   lê a página que o gerador de verdade produziu (o `conftest` da célula a
   materializa). **Um teste que montasse uma página de mentira com o formato
   esperado provaria só que o teste concorda com o código** — e a divergência de
   formato apareceria na tela dele, não no CI.

**A régua, para a próxima vez:** antes de escrever em Python uma regra que já
existe em `painel/logica.js`, pergunte *quem pode chamar a função original?* Se
for o CI ou uma máquina de desenvolvimento, chame por `node -e`. Se for uma
célula em produção, faça o gerador carimbar o resultado e leia o carimbo. Só não
reescreva: as duas cópias vão discordar, e quem descobre é o dono.
