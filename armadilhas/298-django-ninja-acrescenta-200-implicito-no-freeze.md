---
schema_version: 2
armadilha: 298
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: o freeze já pega isto na hora (FAIL, com o diff exato do "200 a mais") — o que faltava era saber de antemão por que ele aparece, para não gastar uma rodada tentando "consertar" o congelado ou o código
sinal:
  - '"200": { "description": "OK" }'
  - "o schema vivo derivou do contrato congelado"
---

# `@router.delete`/`.post` do django-ninja declara um 200 implícito que o freeze não perdoa

**Sintoma.** Você escreve uma porta cujo caminho feliz não é 200 — por exemplo
um `DELETE` que devolve `204 No Content`, sem corpo — declara no
`openapi_extra` só as respostas que a porta realmente dá (204/404/409, digamos),
espelha isso no `contracts/<celula>.openapi.yaml` e roda o freeze. Ele reprova:

```
--- FAIL contrato/alunos ---
@@ -870,6 +870,9 @@
         "responses": {
+          "200": {
+            "description": "OK"
+          },
           "204": { ... }
```

Nem o congelado nem o código "erraram" — o código, de fato, nunca devolve 200.

**Causa.** O `django-ninja` acrescenta uma resposta `200: OK` por padrão a toda
operação, a menos que ela declare explicitamente o schema de resposta
(`response=`) de um jeito que suprima esse default. `openapi_extra["responses"]`
só ACRESCENTA entradas ao dicionário de respostas que o ninja já monta — ele não
troca a base. O schema vivo então fica com uma resposta a mais do que a porta
promete no contrato, e o freeze (que compara os dois documentos byte a byte,
depois de normalizar) enxerga exatamente essa sobra.

**Solução — não é suprimir o 200 implícito, é DEVOLVÊ-LO de verdade.** O padrão
já usado neste projeto (`services/notificacoes/apps/core/api.py`,
`cancelarInscricaoDeAparelho`) é o caminho de menor atrito: toda porta desta
famí­lia responde **200 com um corpo JSON pequeno**, nunca 204 sem corpo.

```python
# Errado — 204 nunca aparece no schema vivo sem trabalho extra, e o freeze reprova
return HttpResponse(status=204)

# Certo — o 200 implícito do ninja É a resposta de sucesso, então ele bate
# com o congelado sem precisar suprimir nada
return JsonResponse({"apagada": True}, status=200)
```

O contrato então declara só `200` (com o corpo) e os erros de verdade
(`404`, `409`, ...) — nenhuma sobra, freeze verde.

**Onde isto NÃO se aplica.** Se a porta genuinamente precisa de um 204 (ou
qualquer outro código fora do 200 implícito) como parte pública do contrato —
por exemplo, um consumidor externo que depende do código exato — o caminho
correto é suprimir o default do ninja com `response=` explícito no decorator, e
então o congelado espelha o 204 de propósito, não por acidente. Isto não foi
necessário aqui: nenhum consumidor desta plataforma distingue 200 de 204, e o
corpo (`{"apagada": true}`) é, se algo, mais informativo para quem debuga um
`curl` manual.

**Onde já mordeu:** `DELETE /pre-matriculas/{id}` (03/09/2026,
`DECISAO-apagar-recusado-definitivamente.md`, PR #919/#920) — a primeira porta
DELETE nova desta plataforma desde que `deleteEnrollment` morreu em 29/08/2026.
