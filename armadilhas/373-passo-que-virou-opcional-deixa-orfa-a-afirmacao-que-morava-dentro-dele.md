---
schema_version: 2
armadilha: 373
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_sessao.py
sinal:
  - a suite inteira verde e o comando mentindo na tela
  - git status limpo sem ninguem ter medido
  - Baseline verde sem baseline nenhum
---

# O passo virou opcional e levou junto a medição que outra frase afirmava: a suíte fica verde e o comando mente na tela

**Data:** 06/09/2026 · **Onde:** `ci/sessao.py`, ao ganhar `--sem-container`
(PR #1211) · **Achado por:** rodar o comando de verdade, não pela suíte.

## Sintoma

Um comando que fecha com um texto de veredito (declaração, resumo, recibo)
passa a afirmar um fato que ninguém mediu naquela execução. A suíte continua
inteiramente verde, porque cada teste mede o caminho que já existia, e o
caminho novo não tem quem cobre o que ele deixou de fazer.

No caso concreto: a Declaração de Abertura do RITOS §1 termina com
`git status: limpo`. A medição dessa limpeza (`git status --porcelain`) morava
dentro do passo do baseline. Com `--sem-container`, o baseline não roda, e a
Declaração seguia afirmando `limpo` sobre uma bancada que ninguém tinha olhado.
Com a pasta suja, o comando assinava uma coisa falsa e saía com exit 0.

## Causa

Uma afirmação e a medição dela estavam no mesmo lugar por acidente de história,
não por desenho. Quando o passo que continha a medição virou condicional, a
afirmação ficou incondicional. As duas metades se separaram em silêncio, porque
nada no código liga uma frase de saída à checagem que a sustenta.

**Por que a suíte não pega.** Os testes do caminho novo provam o que ele FAZ
(criou a bancada, gerou o índice, não subiu container). Ninguém escreve
naturalmente um teste sobre o que o caminho novo DEIXOU de medir: a ausência
não tem nome, não tem chamada de função e não aparece em nenhum diff. É a
Classe "falso-verde" da RETROSPECTIVA-FASE-D §1 na sua forma mais barata de
produzir e mais cara de enxergar.

## Solução

**A pergunta, ao tornar QUALQUER passo opcional:** *quais frases do texto final
continuam sendo impressas, e qual passo media cada uma delas?* Toda afirmação
que sobrevive ao corte precisa de uma destas duas saídas, e nunca de uma
terceira:

1. **A medição migra** para um passo que ainda roda. Extraia-a para um método
   próprio, com nome, e chame-o dos dois caminhos. Foi o que se fez aqui:
   `_exigir_bancada_limpa()` saiu de dentro do baseline e passou a ser chamado
   também pelo último passo do caminho curto.
2. **A afirmação sai do texto**, substituída por `não medido` com o motivo.
   Também foi feito: sem baseline, a Declaração escreve
   `Baseline: não medido (--sem-container: esta bancada não sobe ambiente)`
   em vez de inventar um verde.

O que **não** vale é deixar a frase de pé: dizer menos é honesto, dizer o que
não se conferiu é assinar.

**E o teste que fecha a classe é o do caminho novo com o mundo SUJO**, não o do
caminho novo com o mundo limpo. Uma bancada recém-criada está sempre limpa, e é
por isso que a execução de verdade não acusou nada: o furo só aparece quando a
condição que a frase afirma é FALSA.

```python
def test_sem_ambiente_a_bancada_suja_recusa_a_declaracao_de_limpa():
    mundo = MundoFalso(plano_sem_ambiente(), porcelain=" M ci/sessao.py")
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.codigo == 1
```

## Origem

O furo passou por 111 testes verdes, por 13 muralhas e por uma prova por
mutação de 18 guardas. Quem o achou foi rodar o comando novo de verdade e ler a
tela: a Declaração dizia `git status: limpo` num caminho onde nada mediu isso.
É a prova de fora da RETROSPECTIVA-FASE-D §3 fazendo exatamente o que ela
existe para fazer, e vale como lembrete de que ela não é formalidade de fim de
tarefa.
