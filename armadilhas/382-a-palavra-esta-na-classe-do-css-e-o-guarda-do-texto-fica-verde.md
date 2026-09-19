---
schema_version: 2
armadilha: 382
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: um portão que proibisse `assert "palavra" in html` reprovaria dezenas de guardas legítimos; a cura é a sabotagem deliberada, que já é rito da casa e foi o que pegou este caso
sinal:
  - 'assert "<palavra>" in html'
  - 'class="<prefixo> <palavra>"'
---

# A palavra está na classe do CSS, e o guarda do texto fica verde sem o texto

**Sintoma:** não há nenhum. É esse o problema.

O guarda diz que a tela mostra a palavra, ele está verde, e a tela pode não
mostrar palavra nenhuma.

```python
# o guarda
assert "girando" in html, "o estado precisa estar ESCRITO, e não só colorido"
```

```html
<!-- a tela que passa nesse guarda mostrando só uma bolinha verde -->
<span class="luz girando"></span>
```

**Causa.** O padrão de estado desta casa manda o slug para a tela como CLASSE
do CSS (`class="luz {{ estado }}"`), e a palavra em português sai por um
`{% if %}` ao lado. Os dois carregam a mesma string. Um `in html` cru não
distingue **atributo** de **texto**, então o guarda que existe justamente para
exigir a palavra escrita já é satisfeito pelo atributo que pinta a cor.

O que morre em silêncio é a acessibilidade: a casa decidiu, na `.luz` das
portas principais, que o estado vem escrito e a cor é só o reforço, porque
quem não distingue verde de vermelho precisa LER. Esse guarda parecia proteger
a decisão e não protegia nada.

É prima da `armadilhas/247` pelo mesmo mecanismo (o guarda mede a resposta
crua, e a resposta tem mais coisa que o texto da tela), e é o inverso dela em
gravidade: lá o acidente deixa o teste VERMELHO e alguém vai olhar; aqui ele
deixa VERDE, e ninguém volta.

**Solução.** Exija a palavra **depois do `>`**, no texto que a pessoa lê:

```python
assert re.search(r'class="luz girando"[^>]*>\s*girando', html), (
    "o estado precisa estar ESCRITO no texto, e não só na classe da cor"
)
```

**O que fez este caso aparecer** foi a sabotagem deliberada, e nada mais. Três
sabotagens foram aplicadas de uma vez para provar vermelho→verde; duas
reprovaram, e a terceira (apagar a palavra do `{% if %}`, deixando só a cor)
**passou**. Sem esse passo, o guarda teria entrado no repositório parecendo
proteger a regra.

A lição maior é essa: **prova vermelho→verde não é formalidade de relatório.**
Ela é o único momento em que se descobre que um guarda não guarda. Um guarda
que você não viu falhar é uma linha de teste, não uma garantia.
