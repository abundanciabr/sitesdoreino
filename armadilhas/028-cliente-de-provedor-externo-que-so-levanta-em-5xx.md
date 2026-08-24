<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.9  ·  referencias antigas "ARMADILHAS §4.9" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.9 Cliente de provedor externo que só levanta em 5xx **falha aberto**

**Sintoma:** a API responde **201/200 de sucesso** com os campos do recurso vazios
(`"qr_code": ""`, `provider_payment_id=""`). Nada nos logs, nenhum teste vermelho.
**Causa:** o cliente HTTP só trata o erro grosso:

```python
if resp.status_code >= 500:          # ⟵ 400/401/403/404/429 passam batido
    raise ProviderError(...)
data = resp.json()                   # corpo de ERRO lido como se fosse o recurso
```

O corpo de erro do provedor não tem os campos que o tradutor procura, e
`resposta.get("id", "")` transforma **campo ausente em string vazia** — o erro vira
um objeto de aparência normal e segue adiante como sucesso.
**Três buracos, sempre os mesmos:**
1. **status** — qualquer não-2xx tem de levantar, não só 5xx;
2. **corpo** — `resp.json()` levanta `JSONDecodeError`, que é `ValueError` e **não**
   `httpx.HTTPError`: um `except httpx.HTTPError` não pega uma página HTML de erro
   de CDN/WAF, e ela vira 500 não tratado;
3. **payload** — 2xx não é prova: valide os campos sem os quais o recurso é inútil,
   e **nunca** traduza ausente para `""`.

**Solução:** falhe fechado nos três, com a causa nomeada na mensagem (autenticação,
rejeição, rate limit, indisponibilidade, timeout, corpo ilegível) — no meio de um
incidente, "credencial recusada" e "rate limit" levam a ações opostas. Capture
`httpx.TimeoutException` **antes** de `httpx.HTTPError` (é subclasse dela), porque
num timeout a operação pode ter acontecido do outro lado e um erro de conexão não.
**Onde já estava certo:** `services/checkout/apps/core/clients.py` e
`services/funil/apps/core/clients.py` (`raise_for_status()` / `else None`) — a
armadilha era só de pagamentos, mas confira o seu ao escrever um cliente novo.
**Ao consertar, cuidado com o status novo:** devolver um 502 **não** pode virar
`response={...}` no decorator do django-ninja (§4.2) nem entrar no `openapi_extra`
sem Rito de Contrato — use `JsonResponse(dict, status=502)` direto.
**Origem:** despacho 03 (pagamentos) — o bug estava em produção desde o Prompt 3a e
nenhum dos 19 testes da célula o via (ver §6.9).
