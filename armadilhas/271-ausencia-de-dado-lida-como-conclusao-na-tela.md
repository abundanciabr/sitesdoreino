---
schema_version: 2
armadilha: 271
estado: documentada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: teste
  motivo: os guardas cobrem os três estados da escada na tela e na porta de máquina; o padrão em si não tem varredor, porque `x is None` é legítimo em quase todo outro uso
sinal:
  - 'Você chegou ao último degrau'
---

# A tela lê AUSÊNCIA de dado como CONCLUSÃO, e parabeniza quem não fez nada

**Sintoma.** O aluno abre `/conquistas/` e lê três frases que se contradizem, uma
embaixo da outra:

```
Você está no
Nível 1
Você chegou ao último degrau desta escada. O que vem agora não é um número:
é o que você faz com o que aprendeu.
0 de experiência até aqui
```

Nível 1 e topo da escada ao mesmo tempo, com zero de experiência. Quem lê não
entende se está no começo ou no fim, e o mais provável é concluir que a página
está quebrada. Foi o mantenedor quem viu, no site em produção, em 01/09/2026.

**Causa.** Uma propriedade booleana que junta duas situações opostas debaixo do
mesmo `None`:

```python
@property
def no_topo(self) -> bool:
    return self.xp_do_proximo is None    # "acabou a escada"... ou "não há escada"
```

`xp_do_proximo` é `None` quando a pessoa venceu o último degrau **e também**
quando não existe degrau nenhum ligado. A escada da `gamificacao` nasce inteira
desligada de propósito (`ativa=False`, a economia é dado e o mantenedor a liga em
`/admin/economia/`), então o segundo caso não é raro: **é o estado de todo aluno
da escola**. O template tinha duas frases para três situações, e a que sobrou
para o caso mais comum foi a errada.

A mesma armadilha tem um terceiro caso, ainda mais fácil de não enxergar: a
escola liga o PRIMEIRO degrau e mais nenhum. Aí existe escada, não existe
próximo, e todo aluno "chegou ao topo" no dia em que a economia foi ligada.

**Solução — conte os degraus e devolva o número junto.** Quem consultou o banco
já sabe quantos degraus estão ligados; a tela não pode deduzir isso de um
`None`:

```python
@property
def montada(self) -> bool:      # a escola ligou algum degrau
    return self.degraus > 0

@property
def tem_proximo(self) -> bool:  # há barra de progresso a desenhar
    return self.xp_do_proximo is not None

@property
def no_topo(self) -> bool:      # subiu uma escada de verdade
    return self.degraus >= 2 and self.xp_do_proximo is None
```

E o template ganha a terceira frase, a que faltava: **a escada ainda está sendo
montada**. Ausência não é conquista.

**A régua, para reconhecer o padrão em qualquer tela.** Todo campo opcional que
chega a uma tela responde a duas perguntas diferentes ao mesmo tempo: *"o valor
não existe"* e *"o valor é o fim da faixa"*. Sempre que uma frase de PARABÉNS
depender de um `None`, `0` ou lista vazia, pergunte quem produz esse vazio no
sistema recém-instalado — se a resposta for "todo mundo, no primeiro dia", a
frase está errada para o caso mais comum que ela vai viver. É a mesma família de
`armadilhas/240` (o pipe que confunde "não respondeu" com "respondeu vazio"), só
que a vítima aqui é o aluno, não o mantenedor.

**O irmão do defeito, que veio junto.** A porta de máquina da mesma célula
calculava o próximo degrau sem filtrar `ativa=True`, enquanto a tela sempre
filtrou: a mesma escada dava duas respostas conforme quem perguntasse, e o
quadrinho de progresso da home prometia um degrau que o mantenedor não abriu.
Quando uma conta mora em dois lugares, o dia em que uma delas ganha um filtro é
o dia em que as duas passam a discordar em silêncio.

**Origem:** 01/09/2026, PR #838. Achado por LEITURA de tela, não por teste: o
guarda que existia (`test_no_ultimo_degrau_a_tela_nao_promete_um_proximo`) ficava
verde justamente por montar o cenário fraco de UM degrau só, que é o caso em que
a frase do topo não deveria aparecer. Cenário fraco não protege: ele carimba.
