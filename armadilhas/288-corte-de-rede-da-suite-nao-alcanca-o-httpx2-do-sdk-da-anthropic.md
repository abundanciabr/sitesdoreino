---
schema_version: 2
armadilha: 288
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  motivo: o corte de rede de `services/forum/tests/conftest.py` passou a trocar TAMBÉM `httpx2.HTTPTransport.handle_request`, e o dublê dos testes do agente troca essa mesma função por uma que responde. Nenhuma muralha consegue ver isto de fora: para o CI, uma suíte que chama a internet de verdade é uma suíte verde.
sinal:
  - suíte que se declara sem rede e passa a depender de uma biblioteca nova de HTTP
  - conftest que corta `httpx.Client.post` mas o SDK chama `Client.send`
  - dependência nova cujo `pip show` lista um cliente HTTP diferente do que a célula já usava
---

# O corte de rede da suíte não alcança o `httpx2` do SDK da Anthropic: os testes "sem rede" chamam a API paga de verdade

**Sintoma.** Não há nenhum. A suíte fica verde, o `conftest.py` promete por
escrito que *"a suíte do fórum não fala com a rede"*, e mesmo assim cada
execução dos testes do agente de IA sai para `api.anthropic.com`, com a chave da
máquina de quem rodou, gastando dinheiro. Se a máquina não tiver chave, o teste
falha com uma mensagem de autenticação que parece bug do código; se tiver, ele
passa e a fatura cresce em silêncio.

**Causa.** São duas bibliotecas com o mesmo sobrenome e pacotes diferentes.

A célula `forum` já falava com `identidade`, `alunos`, `catalogo` e
`gamificacao` por **`httpx`**, e o corte da suíte era este:

```python
monkeypatch.setattr(httpx.Client, "get", recusa)
monkeypatch.setattr(httpx.Client, "post", recusa)
```

O SDK `anthropic` 1.x **não usa `httpx`**. Ele roda sobre **`httpx2`**, uma
distribuição separada que entra junto na instalação e convive lado a lado com a
outra. Duas consequências, e cada uma sozinha já basta para o furo:

1. `httpx2.Client` é outra classe. Trocar método em `httpx.Client` não a toca.
2. Mesmo dentro do `httpx2`, o SDK chama **`Client.send`**, não `.get` nem
   `.post`. O corte copiado para a classe nova, do jeito óbvio, continuaria sem
   pegar nada.

O engano é confortável porque tudo o que se vê é familiar: o `import` parece o
mesmo, a API parece a mesma, e o `pip install` não avisa que trouxe um segundo
cliente HTTP para dentro da casa.

**Solução.** Cortar no **transporte**, que é o único ponto por onde os dois
saem para o sistema operacional, e cortar os dois:

```python
import httpx
import httpx2

monkeypatch.setattr(httpx.Client, "get", recusa)
monkeypatch.setattr(httpx.Client, "post", recusa)
monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", recusa_httpx2)
```

O transporte não é só o lugar mais seguro: é o lugar mais **útil**. Como
`httpx2.HTTPTransport.handle_request` é a fronteira exata entre o SDK e a rede,
o teste que quer um dublê troca essa mesma função por uma que devolve uma
resposta de mentira, e com isso o SDK **monta o request de verdade e lê a
resposta de verdade**. É a cura da `armadilhas/061` de graça: um erro no jeito
de chamar a API aparece no teste, em vez de aparecer na primeira conta paga.

```python
def falso(self, request):
    capturado["corpo"] = json.loads(request.content)
    return httpx2.Response(200, json=corpo_de_resposta("..."), request=request)

monkeypatch.setattr(httpx2.HTTPTransport, "handle_request", falso)
```

**A régua que fica, e ela é maior que a Anthropic:** toda vez que uma célula
ganhar uma dependência que fala HTTP, pergunte **por qual cliente ela sai** antes
de confiar no corte de rede que já existe. Um `conftest` que promete isolamento é
uma garantia declarada, e garantia declarada sem mecanismo apodrece
(`RETROSPECTIVA-FASE-D` §2). Aqui a diferença é que a garantia apodreceu
**sem mudar de texto**: a frase do docstring continuou verdadeira sobre o
`httpx` e virou mentira sobre a célula inteira, no mesmo commit em que a
dependência entrou.

**Vale também para o contrário.** Se um dia alguém "arrumar" o `requirements.txt`
trocando `httpx` por `httpx2` para ter um cliente só, os dublês de `identidade` e
`alunos` param de dublar e a suíte passa a sair para a rede pelo outro lado. Os
dois cortes existem porque os dois clientes existem, e sair de um deles é uma
edição que precisa mexer no `conftest` na mesma passada.
