# 292 — Teste que fatia o documento INTEIRO quebra quando a página ganha uma peça no topo

**Sintoma.** Uma mudança de layout que ninguém pediu para medir derruba testes de
outras telas, com mensagens que não falam do layout:

```
assert reverse("escola") not in html[:sistema]
E   AssertionError

AssertionError: ../ respondeu 404
E   assert 404 == 200
```

Nenhuma das duas menciona menu, moldura ou navegação. A primeira parece dizer
que os dois painéis voltaram a se confundir; a segunda, que um arquivo do
painel sumiu. As duas estão certas sobre o que mediram e erradas sobre o que
aconteceu.

**Causa.** Os dois guardas mediam o DOCUMENTO INTEIRO para responder a uma
pergunta sobre uma PEÇA dele.

O primeiro fatiava o HTML pela posição de um rótulo e afirmava que o endereço
do cartão estava na fatia da frente:

```python
sistema = html.index("Abrir o painel do sistema")
assert reverse("escola") not in html[:sistema]   # "antes do cartão não há Escola"
```

Isso valia enquanto acima do conteúdo não houvesse nada. No dia em que a área
ganhou um menu no topo (`services/admin/apps/core/moldura.py`), a fatia "antes
do rótulo" passou a conter o menu inteiro, com um link para a Escola. O guarda
ficou vermelho sem que a ligação que ele protege tivesse mudado.

O segundo varria todo `src=`/`href=` da página e cobrava 200 de cada um, como
se todo endereço escrito numa página fosse um arquivo que ela carrega. Um link
de NAVEGAÇÃO (`href="../"`, a porta de volta) não é isso, e o varredor o pediu
ao servidor de arquivos, que respondeu 404 com toda a razão.

**Solução.** Meça o componente, não o documento.

No primeiro, a pergunta nunca foi "o que existe antes deste texto na página",
e sim "para onde aponta o cartão que traz este texto". A resposta é o `href`
mais próximo ANTES do rótulo, e a asserção fica mais apertada, não menos:

```python
def _href_do_cartao(html: str, rotulo: str) -> str:
    ate = html.index(rotulo)
    inicio = html.rindex('href="', 0, ate) + len('href="')
    return html[inicio : html.index('"', inicio)]

assert _href_do_cartao(html, "Abrir o painel do sistema") == reverse("painel")
```

Igualdade por cartão em vez de presença no documento: trocar os dois cartões de
lugar continua reprovando, e qualquer coisa nova acima do conteúdo passa a ser
irrelevante para o guarda, que é como deveria ter sido desde o começo.

No segundo, separe os dois tipos de endereço e cubra o que você excluiu:

```python
# `..` sobe uma pasta: é porta de saída, não arquivo que esta página serve.
and not alvo.startswith("..")
```

...com um teste NOVO ao lado, cobrando que a porta continue existindo. Sem ele,
a linha de exclusão viraria um lugar onde um link pode sumir em silêncio, que é
como um portão morre.

**A régua, em uma pergunta.** Antes de escrever `html[:x]`, `html.index(...)` ou
uma varredura de todo `href` da página, pergunte: *isto continua verdadeiro se
amanhã a página ganhar um cabeçalho, um menu ou um rodapé?* Se a resposta for
não, o guarda está medindo a moldura junto com o quadro, e vai acusar a moldura
de ter mexido no quadro.

**Onde isto mordeu.** 02/09/2026, no PR que deu menu e rodapé próprios a toda
tela de `/admin`. Dois testes vermelhos em telas que o PR não tocou, e os dois
por esta mesma causa. O custo foi baixo porque os guardas falaram na hora; o
caro seria o contrário: um guarda que continuasse verde depois de o layout
mudar, ainda medindo uma posição que não quer dizer mais nada.

**Parente próximo.** `armadilhas/242` (peça que depende de alguém lembrar de
incluí-la) é a razão de a moldura ter nascido como processador de contexto, e
portanto a razão de ela ter aparecido em todas as páginas de uma vez. Esta
armadilha é a fatura dessa mudança do lado dos testes.
