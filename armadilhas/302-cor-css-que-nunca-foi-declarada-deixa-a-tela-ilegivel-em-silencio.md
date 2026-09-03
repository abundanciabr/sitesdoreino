---
schema_version: 2
armadilha: 302
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: CI
  dono: services/admin/tests/test_toda_cor_usada_tem_dono.py
  motivo: todo nome usado em `var(--x)` num template da área precisa estar declarado em algum `:root` que o navegador enxergue; a regra é mecânica e não julga contraste
sinal:
  - "var\(--cartao"
  - "var\(--borda\)"
---

# Uma cor CSS que ninguém declarou deixa a tela ilegível, e nada fica vermelho

**Sintoma:** o mantenedor abre uma tela do Admin e não consegue LER os cartões.
O texto está lá, o HTML está inteiro, a página responde 200, todos os testes
estão verdes e o deploy foi conferido. Numa captura de tela parece escolha de
design ruim, e não defeito. As palavras dele em 03/09/2026, sobre
`/admin/caixa/robos/`: *"está bastante confusa pra mim, eu não estou
conseguindo usar, acompanhar ela. Começando por esse texto que eu não estou
conseguindo ver corretamente."*

**Causa.** Uma linha de estilo daquela aba:

```css
.cartao-robo { background: var(--cartao, #fff); border-left: 5px solid var(--borda); }
```

**`--cartao` e `--borda` nunca existiram.** O `:root` de `admin/base.html`
declara `--fundo`, `--painel`, `--linha`, `--texto`, `--texto-2`, `--texto-3` e
as quatro cores de estado, e mais nada. Quem escreveu chutou o nome pela
intenção ("é o cartão, deve ser `--cartao`") e nunca abriu a folha.

Um nome inventado não é erro para o navegador. Ele tem duas saídas, e as duas
são silenciosas:

1. **Com valor de reserva** (`var(--cartao, #fff)`) ele usa a reserva. O cartão
   virou BRANCO numa área de fundo escuro, enquanto o texto continuava com a cor
   da área (`--texto: #e6e9ef`, quase branco). Quase branco sobre branco.
2. **Sem valor de reserva** (`var(--borda)`) ele descarta a declaração inteira,
   e `border-color` cai no valor inicial: `currentColor`. A borda passa a ter a
   cor do TEXTO — clara demais, num lugar onde se esperava uma linha discreta.

Nenhuma das duas aparece no console, em log, em teste ou em revisão de código:
`var(--cartao, #fff)` lido em um diff parece exatamente uma linha correta.

**Solução.** Use os nomes que existem — `--painel` para fundo de cartão e
`--linha` para borda — e nunca crave `#fff` numa área de fundo escuro. Antes de
inventar um nome, abra o `:root` da folha-mãe da célula.

O guarda que fecha a classe inteira é uma varredura estática, e roda em toda a
pasta de templates da célula:

```python
USO = re.compile(r"var\(\s*(--[a-z0-9-]+)")
DECLARACAO = re.compile(r"(--[a-z0-9-]+)\s*:")
# declaradas = as do base.html + as do PRÓPRIO arquivo (base_publico tem :root próprio)
```

Ele responde uma pergunta só, mecanicamente: **todo nome usado está declarado
em algum lugar que o navegador vai enxergar?** Contraste ele não julga — isso é
olho humano, e um portão que fingisse medi-lo seria pior que nenhum.

**Pode a folha antes de medir** (`armadilhas/247`): este arquivo mesmo escreve
`var(--cartao, #fff)` para explicar o defeito, e um guarda ingênuo se
autoreprovaria no comentário que o documenta.

**O que prova que a cura vale a pena.** No dia em que foi achado, o mesmo erro
estava em TRÊS telas escritas por três sessões diferentes: a aba dos robôs
(`--cartao` e `--borda`), a de exportar a Caixa (as duas de novo) e a de turmas
(`--borda`). Nenhuma delas quebrou nada visível para quem escreveu o código —
só para quem abriu a página. É a `RETROSPECTIVA-FASE-D` §2 outra vez: garantia
sem mecanismo não é garantia, e "confira o nome da variável" é conselho, não
mecanismo.

**A lição maior, e ela não é sobre CSS.** Todo defeito que só aparece na TELA
do dono nasce invisível para o robô, porque o robô mede o HTML e ele mede a
imagem. Sempre que uma mudança for de aparência, renderize a página com dados
de verdade e OLHE — ou entregue a prévia para quem vai olhar. Foi o que fechou
esta: a página renderizada com as 101 tarefas reais, enviada ao mantenedor
antes do deploy.
