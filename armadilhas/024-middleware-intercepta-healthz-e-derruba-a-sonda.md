<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.5  ·  referencias antigas "ARMADILHAS §4.5" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.5 Middleware intercepta `/healthz` e derruba a sonda

**Sintoma:** `/healthz` passa a devolver 404 depois de instalar o middleware
CONV-SITE; o teste de fumaça quebra e, em produção, o container ficaria "unhealthy".
**Causa:** o middleware roda em **toda** requisição. `/healthz` chega sem Host de site
(é sonda do container e do gateway) e não pode depender do catálogo estar de pé.
**Solução:** isente os caminhos que não pertencem a nenhum site:

```python
CAMINHOS_SEM_SITE = ("/healthz", "/static/")
if request.path.startswith(CAMINHOS_SEM_SITE):
    return self.get_response(request)
```

**Origem:** Prompt 4 (checkout).
