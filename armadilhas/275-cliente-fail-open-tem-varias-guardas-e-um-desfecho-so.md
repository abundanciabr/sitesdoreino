---
schema_version: 2
armadilha: 275
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão consegue ver que o dublê de um teste dispara TAMBÉM a guarda vizinha, porque as duas produzem o mesmo valor de retorno e o teste não sabe por qual delas passou. O que acha o caso é o rito da mutação deliberada (RITOS §2 peça 3), guarda por guarda; este arquivo é a régua de como montar o dublê para que a mutação tenha o que matar.
sinal:
  - mutação que apaga uma guarda de um cliente fail-open e o teste continua verde
  - mais de um `return` de lista vazia seguido, numa função que promete nunca levantar
  - um dublê de erro que quebra mais de uma regra de uma vez
---

# Cliente que falha aberto tem várias guardas e UM desfecho só: cada teste passa pela guarda errada, e a mutação é a única que percebe

**Sintoma.** Você escreveu um cliente de outra célula no molde da casa: falha
ABERTA, todo tropeço vira lista vazia, nada levanta. Escreveu um teste por modo
de falha, todos verdes. Foi provar por mutação, apagou a guarda de status HTTP,
e o teste do status **continuou verde**:

```
tests/test_cliente_do_forum.py::test_status_fora_de_200_devolve_lista_vazia PASSED
```

Nenhum erro, nenhum aviso. A guarda que você acabou de apagar não fazia falta
para nenhum teste.

**Causa.** Uma função que falha aberto tem N regras e **um desfecho só**:

```python
if resposta.status_code != 200:
    return []          # guarda 1
corpo = resposta.json()  # (ValueError também vira [])   guarda 2
if not isinstance(corpo, list):
    return []          # guarda 3
for item in corpo:
    if not all(c in item for c in CAMPOS):
        return []      # guarda 4
```

O teste só consegue olhar o valor de retorno, e ele é `[]` nas quatro. Se o
dublê do teste do status responde **401 com `{"erro": "x"}`**, ele quebra DUAS
regras de uma vez: o número e a forma do corpo. Apagada a guarda 1, o corpo cai
na guarda 3, o retorno continua `[]`, e o teste continua verde. Ele nunca mediu
o status; media "alguma coisa deu errado".

É a família de falso-verde da `RETROSPECTIVA-FASE-D` §1 na sua forma mais
discreta: **asserção com mais de uma causa suficiente**, sem nenhum `if`
errado no código de produção e sem nada estranho no teste. Diferente da
`armadilhas/269`, onde o próprio código de produção conserta a mutação; aqui
quem conserta é a guarda VIZINHA, e é por isso que o caso escapa de quem já
conhece a 269. Diferente também da `armadilhas/268`: lá a mutação dá vermelho
sem provar nada; aqui ela dá **verde** sem provar nada, que é pior, porque a
cerimônia da mutação foi cumprida e o desfecho parece dizer "a guarda não faz
falta, apague".

**A segunda metade da armadilha, e é onde ela morde de volta:** ao consertar,
é fácil escolher um dublê que troca uma segunda causa por outra. O teste de
"corpo fora do contrato" respondia `{"topicos": [...]}` com 200. Apagada a
guarda 3, o `for` percorre as CHAVES do dicionário, cada chave é `str`, a
guarda 4 pega, e o teste segue verde. Um texto solto faz o mesmo, letra por
letra. Só um valor **não percorrível** distingue as duas.

**Solução, em uma régua: monte cada dublê para que ele passe por TODAS as
outras guardas e caia só na sua.**

```python
# ERRADO: 401 com corpo torto — quebra o status E a forma
mock.get(URL).mock(return_value=httpx.Response(401, json={"erro": "x"}))

# CERTO: 401 com o corpo que o contrato promete — só o número está errado
mock.get(URL).mock(return_value=httpx.Response(401, json=[_topico()]))

# ERRADO: corpo fora de forma que ainda é percorrível
httpx.Response(200, json={"topicos": [_topico()]})

# CERTO: parametrizado, com um caso NÃO percorrível que só a guarda 3 pega
@pytest.mark.parametrize("corpo", [{"topicos": [...]}, "texto", 5, True])
```

E rode a mutação **guarda por guarda**, nunca uma vez pelo arquivo inteiro: a
suíte fica verde no agregado e você não descobre qual das quatro estava sendo
carregada pelas outras.

**Cuidado com o `json=None`:** ele não vira o JSON `null` no `httpx`. O corpo
sai VAZIO, `resposta.json()` levanta `ValueError`, e o caso cai na guarda 2 —
outra segunda causa suficiente, disfarçada de conserto. Use `5` ou `True`.

**Onde isto foi medido:** 02/09/2026, na fundação da Galeria da `gamificacao`
(TAR-102), no cliente de `listRecentTopics` do fórum. Das 13 mutações do
despacho, 11 mataram de primeira e **duas ficaram verdes**, as duas descritas
aqui, nos dois testes que o próprio brief pedia em letras ("fórum fora do ar /
env ausente / corpo fora do contrato ⇒ lista vazia"). Os dois testes tinham
nome certo, docstring certa e asserção certa, e guardavam a guarda do vizinho.
Custo do conserto: dez minutos e sete linhas de dublê. Custo de não rodar a
mutação: duas guardas na `main`, verdes, guardando nada — e o dia em que uma
delas fosse "simplificada" ninguém ficaria vermelho.
