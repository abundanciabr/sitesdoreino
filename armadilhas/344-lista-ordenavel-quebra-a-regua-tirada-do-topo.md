---
schema_version: 2
armadilha: 344
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: `ci/tests` nao alcanca telas de celula; o guarda mora na suite da celula (services/admin/tests/test_caixa_no_admin.py::test_a_regua_da_barrinha_nao_muda_de_escala_com_a_ordem), que pede a tela FORA da ordem padrao e confere que a maior plateia continua a regua. Nenhum portao generico consegue: seria preciso entender que aquele indice zero era um max disfarcado.
sinal:
  - `passo-1[1-9]` numa barra que so tem CSS ate `passo-10`
  - barra de proporcao sem largura depois de a lista ganhar ordenacao
---

# Dar ordenação a uma lista quebra toda régua que alguém tirou do topo dela

**Sintoma.** Uma lista que sempre saiu ordenada por um número ganha um seletor de
ordem. Os testes continuam verdes, a lista reordena certo — e uma barra de
proporção ao lado de cada linha aparece **sem largura nenhuma**, ou estourando a
caixa, em toda ordem que não seja a antiga.

**Medido em 05/09/2026**, na tela "Quem está esperando" da Caixa
(`services/admin/apps/core/caixa.py`). A régua da barrinha era esta linha:

```python
"maior_plateia": em_aberto[0]["pessoas"] if em_aberto else 1,
```

Ela estava CERTA enquanto a lista tinha uma ordem só: ordenada por plateia
decrescente, a primeira **é** a maior. A linha não dizia "a primeira"; ela dizia
"a maior", e as duas frases eram a mesma até o dia em que deixaram de ser. Com
`?ordem=antigas`, a primeira passou a ser uma ideia de 30 pessoas num quadro cuja
maior tem 40 — e o template calcula a largura em passos de 10%:

```django
{% widthratio i.pessoas maior_plateia 10 as passo %}
<span class="barra-gente passo-{{ passo }}"></span>
```

40 sobre 30 dá `passo-13`. O CSS só define `.passo-0` a `.passo-10`, então a
classe existe, o HTML é válido, nenhum erro é levantado e a barra da ideia MAIS
importante da tela é a única que some.

**Causa.** É uma invariante que morava no chamador e não estava escrita em lugar
nenhum: *"o primeiro item é o maior"*. Ordenação nova apaga essa invariante sem
tocar na linha que dependia dela, e o compilador, o teste e a revisão não veem
nada — o código continua igual, o mundo em volta é que mudou. A família é a mesma
de `armadilhas/148` (mapa velho que envelhece em silêncio), aplicada a uma
suposição em vez de a um documento.

**Onde mais isso mora.** Procure, na mesma passada em que você acrescentar
qualquer ordenação, por tudo que leia a lista **por posição** em vez de por
valor: `lista[0]`, `[:3]`, `|first` no template, "o destaque", "o campeão", "o
mais antigo", e qualquer denominador de proporção. Cada um é uma régua tirada do
topo.

**Solução.**

1. **Diga o que você quer dizer.** `max((i["pessoas"] for i in abertas),
   default=1)` não depende de ordem nenhuma, e continua verdadeiro em qualquer
   ordem futura. O `or 1` no fim evita a divisão por zero quando a maior plateia
   for zero — que `[0]` também não tratava.
2. **Meça a régua ANTES da peneira, não depois.** Uma barra cuja escala muda com
   o filtro deixa de poder ser comparada com a que estava ali um clique atrás.
3. **O guarda pede a tela FORA da ordem padrão.** Um teste que só abre a página
   sem parâmetro fica verde com o defeito no lugar, porque na ordem padrão as
   duas implementações concordam — é a mesma armadilha de cenário incompleto de
   `armadilhas/267`. O guarda desta tela pede `?ordem=antigas` e confere que
   `passo-11`, `passo-13` e parentes não existem na página.

**A pergunta que acha isto em revisão:** *que linha deste arquivo só está certa
porque a lista chega numa ordem específica?* Se a resposta demorar, procure por
`[0]` e por denominador.
