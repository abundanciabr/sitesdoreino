---
schema_version: 2
armadilha: 554
estado: documentada
degrau: 1
confianca: alta
custo_por_queda: medio
gatilho:
  - ci/operacoes_vps.py
sinal:
  - "inbox_consultada.*false"
guarda:
  tipo: nenhum
  motivo: "e comportamento do ambiente sandbox da Appmax, fora deste repositorio; nenhum portao local faz o sandbox deles emitir o webhook que ele nao emite"
licao: "No sandbox da Appmax, o webhook de cartao aprovado nao chega a inbox (3 referencias do cartao 0010 ausentes, runs 36326584933, 36326621783, 36326661927 de appmax-inbox-latencia); a aprovacao chega so pela resposta sincrona de criar_intent. Latencia de webhook de cartao NAO se mede no sandbox, so em producao."
---

# 554: no sandbox da Appmax, cartão aprovado não gera webhook, só resposta síncrona

**Data:** 27/09/2026 · **Onde:** `ci/operacoes_vps.py`
(`appmax-inbox-latencia`), sandbox Appmax, obra Appmax · **Custo evitado:**
insistir em medir latência de webhook de cartão no sandbox achando que a
inbox de pagamentos está com defeito, quando o ambiente de testes da Appmax
simplesmente não emite esse aviso para cartão.

## Sintoma

Três referências do cartão de teste `0010`, medidas com
`appmax-inbox-latencia` em três execuções distintas (runs 36326584933,
36326621783 e 36326661927), voltaram sem nenhum registro na inbox de
pagamentos, mesmo a compra tendo sido aprovada. O cartão foi aprovado — a
resposta síncrona da chamada de pagamento confirma — mas o webhook
correspondente nunca chegou.

## Causa

O sandbox da Appmax, para o método cartão, comunica a aprovação apenas pela
**resposta síncrona** da chamada de criação da intent de pagamento
(`PagamentosClient().criar_intent`, `services/checkout/apps/core/api.py`).
Ele não dispara o webhook assíncrono de "cartão aprovado" que o ambiente de
produção envia. Como a inbox de pagamentos só é populada por webhook, ela
fica vazia para cartão no sandbox, mesmo com a compra efetivamente
aprovada.

## Solução

Não trate ausência de registro na inbox, para cartão, como falha de
processamento no sandbox: confirme a aprovação pela resposta síncrona da
chamada, não pelo webhook. E não tente medir latência de aviso de cartão no
sandbox — essa medição só é possível em produção, onde o webhook existe. Se
o objetivo é medir latência de webhook, use Pix (que o sandbox notifica por
webhook normalmente) ou meça em produção com o devido cuidado.

## Origem

Obra Appmax, sessão de coordenação de 27/09/2026; `ci/operacoes_vps.py`
(`appmax-inbox-latencia`); runs 36326584933, 36326621783, 36326661927;
cartão de teste `0010`.
