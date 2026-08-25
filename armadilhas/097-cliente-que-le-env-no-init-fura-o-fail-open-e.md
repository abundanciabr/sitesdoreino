# Cliente que lê env no `__init__` fura o fail-open: `KeyError` vira **HTTP 500 em toda página**, com o deploy verde

**Sintoma:** a célula promete, por escrito e com testes, que uma dependência
fora do ar **não derruba** a página — e mesmo assim o site inteiro devolve 500.
Só para quem tem cookie no navegador; quem chega limpo vê 200. O
`deploy-celula` fica **verde**, o `/healthz` responde 200, e a suíte da célula
passa inteira.

```python
class IdentidadeClient:
    def __init__(self) -> None:
        self.base = os.environ["IDENTIDADE_API_URL"].rstrip("/")   # <- aqui
        self.token = os.environ["IDENTIDADE_API_TOKEN"]

    def obter_sessao(self, cookie):
        try:
            r = http().get(...)          # o try que "garante" o fail-open
        except httpx.HTTPError:
            return None                  # ... e que nunca chega a rodar
```

**Causa:** o `try/except httpx.HTTPError` protege a **chamada de rede**, mas o
`__init__` roda **antes** dele. `KeyError` não é `httpx.HTTPError`: ele sobe
pelo middleware, pelo `{% if request.ator %}` do template e vira 500.

Três coisas que tornam esta armadilha mais cara do que parece:

1. **Falha de configuração é MAIS provável que falha de rede.** Basta uma
   variável não colada no servidor — que é justamente o passo humano de todo
   rollout (`ARMADILHAS-OPERACAO.md` §1: H18, H19, H20…). O caso testado
   (dependência fora do ar) é o raro; o não testado é o comum.
2. **É invisível para quem testa.** O caminho preguiçoso só resolve a sessão se
   houver cookie, então um navegador anônimo — ou o smoke de deploy, que bate
   na raiz sem cookie — recebe 200. Quem já visitou o site uma vez recebe 500.
3. **Renomear variável arma a bomba.** O PR que troca `SUGESTOES_API_URL` por
   `IDENTIDADE_API_URL` faz a célula passar a ler um nome que **não existe** no
   servidor. O merge parece inofensivo; o efeito é o site fora do ar.

**Solução — ler no PONTO DE USO, com `.get()`, e desistir SEM tocar a rede:**

```python
def _configuracao(self) -> "tuple[str, str] | None":
    base = (os.environ.get("IDENTIDADE_API_URL") or "").strip().rstrip("/")
    token = (os.environ.get("IDENTIDADE_API_TOKEN") or "").strip()
    return (base, token) if base and token else None

def obter_sessao(self, cookie):
    config = self._configuracao()
    if config is None:
        logger.error("sessao: IDENTIDADE_API_URL/IDENTIDADE_API_TOKEN ausentes")
        return None          # fail-OPEN de verdade
    ...
```

Desistir **sem tentar a rede** é metade da correção: esperar o timeout (2s)
para descobrir que não há endereço atrasaria toda página do site.

**E o guarda vem em PAR** — um prova que a página abre, outro prova que ela nem
tentou a rede:

```python
@pytest.mark.parametrize("ausente", ["IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN"])
def test_sem_configuracao_a_pagina_abre_como_visitante(client, rede, monkeypatch, ausente):
    monkeypatch.delenv(ausente, raising=False)
    assert client.get("/pt-br/", HTTP_COOKIE=COOKIE).status_code == 200

def test_sem_configuracao_nao_custa_salto_de_rede(client, rede, monkeypatch):
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)
    client.get("/pt-br/", HTTP_COOKIE=COOKIE)
    assert _chamadas_de_sessao(rede) == []
```

**Por que a suíte não pegava:** o `conftest.py` fazia `monkeypatch.setenv` das
variáveis em **todos** os testes (`autouse`). `grep -c delenv` na suíte
inteira: **0**. A suíte provava resiliência a falha de rede e nunca havia
testado falha de configuração — "garantia sem mecanismo" (RETROSPECTIVA §2) na
forma mais pura.

**Parente próximo, no mesmo arquivo:** `resposta.json()` fora do `try`.
`json.JSONDecodeError` é `ValueError`, **não** é `httpx.HTTPError` — um `200`
com corpo de página de erro de proxy fura o fail-open pelo mesmo caminho. É a
família do *2xx não é sucesso* (RETROSPECTIVA §4). Mova o `.json()` para dentro
do `try` e acrescente `ValueError` ao `except`.

**Como varrer o repositório inteiro:**

```bash
grep -rn 'os\.environ\[' services/*/apps/core/clients.py
```

Toda ocorrência num consumidor **fail-open** é esta armadilha. Num consumidor
**fail-closed** (a Caixa conferindo matrícula, por exemplo) é aceitável — lá o
correto é fechar a porta —, mas prefira `exigir()` com mensagem nomeando a
variável, que é o padrão da casa.

**Origem:** auditoria de duas bancas do login do site, 25/08/2026. Quatro
cadeiras independentes (IAM, confiabilidade, acesso público e arquitetura)
acharam o mesmo ponto, no PR #145. O mesmo padrão já estava vivo em produção,
em `SugestoesClient` — funcionando só porque o env fora colado à mão. Provado
por mutação: voltar o `os.environ[...]` reprova exatamente os três guardas
novos.
