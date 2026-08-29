---
schema_version: 2
armadilha: 21
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: sino
  dono: ci/sino_das_armadilhas.py
sinal:
  - `ConfigError: Schema for status \d+ is not set`
---

<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.2  ·  referencias antigas "ARMADILHAS §4.2" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.2 `ConfigError: Schema for status 201 is not set in response`

**Sintoma:** handler devolve `(201, {...})` e a rota estoura.
**Causa:** rota **sem** `response=` no decorator só aceita 200.
**Solução:** devolva `django.http.JsonResponse(dict, status=N)` direto — passa batido
pelos `response_models` por completo.
**NÃO resolva com `response={200: ..., 201: ...}`:** qualquer valor não-`None` ali vira
um `ninja.Schema` dinâmico que pode vazar para `components.schemas` do documento
exportado e **quebrar o freeze de contrato**.
**Origem:** Prompt 3a (pagamentos, PR #16).
