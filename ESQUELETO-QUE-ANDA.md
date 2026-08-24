# O ESQUELETO QUE ANDA — Marco Zero da Plataforma

Antes de qualquer feature real, UMA transação sandbox atravessa TODAS as células.
Fininha, feia, mas de ponta a ponta. Integração deixa de ser risco futuro e vira
fato do dia 3 — cada feature depois disso apenas engorda um esqueleto que já anda.

## O caminho da transação

```
[seed]      catalogo:  Site (host = domínio de operações) + produto "Curso Esqueleto"
                       (R$ 9,90 → 990 cents) + oferta publicada NESSE site
   ↓
[sessão]    checkout:  POST /sessoes {offer_slug: "curso-esqueleto"}
   ↓
[pedido]    checkout:  POST /sessoes/{id}/pedido — snapshot congela (INV-P1/P2),
   ↓                   intent nasce em pagamentos via API interna (INV-P4)
[cobrança]  pagamentos: sandbox MP (TEST-...) cria o pagamento
   ↓
[webhook]   pagamentos: aprovação chega, assinada (INV-P10), idempotente (INV-P3)
   ↓
[outbox]    pagamentos: pagamento.aprovado.v1 na outbox NA MESMA transação (INV-P6)
   ↓
[relay]     Huey publica no Redis Streams (stream eventos.pagamento.aprovado)
   ↓
[matrícula] alunos: consumer matricula sob lock, idempotente por order_id (INV-P5)
   ↓
[verificação] GET /api/alunos/alunos/{email}/matriculas ⇒ matrícula ativa ✅
              (paralelo: checkout marcou pedido "pago"; mensageria logou boas-vindas)
```

## O problema do webhook em cada ambiente (honestidade operacional)

- **LOCAL:** o MP não alcança `localhost`. A célula pagamentos expõe, **somente com
  `DEBUG=1`**, o endpoint `POST /debug/simulate-webhook` que constrói um webhook
  real assinado com o `MP_WEBHOOK_SECRET` local e o entrega a si mesma — validando
  o caminho inteiro (assinatura → idempotência → outbox → relay → consumers).
  Em `DEBUG=0` esse endpoint NÃO EXISTE (nem 403 — 404). Os curls locais do
  esqueleto enviam `-H "Host: <domínio-de-operações>"` para o middleware
  CONV-SITE resolver o site.
- **VPS (staging = a própria produção antes do DNS público):** cartão sandbox com
  o cartão de teste APRO aprova de verdade e o webhook REAL do MP chega em
  `/api/pagamentos/webhooks/mp/card` — o esqueleto anda de ponta a ponta sem simulação.
  Este é o critério final da Etapa D.

## O comando único (raiz do repo)

```make
esqueleto:
	bash e2e/esqueleto.sh   # sobe compose, seeda, executa o caminho acima via curl,
	                        # imprime cada elo com ✅/❌ e falha se qualquer elo falhar
```

`make esqueleto` roda: (1) local com webhook simulado — no CI a cada PR de célula
que participe do caminho; (2) manual na VPS com cartão APRO — uma vez por marco.

## Critérios de aceite (Etapa D só fecha com os quatro)

1. `make esqueleto` verde LOCALMENTE (webhook simulado assinado).
2. Esqueleto verde NA VPS com cartão sandbox APRO e webhook real do MP.
   ☐ **em aberto por decisão do mantenedor (23/08/2026): "parar e deixar
   registrado".** Não é só "rodar um teste": depende de (a) construir a
   confirmação de cartão — não há caminho público para pagar um cartão hoje (o
   Card Payment Brick nunca foi montado) — e (b) do mantenedor registrar o
   webhook no painel do MP e pôr o secret na VPS (INV-P8/Lei 5). Mapa completo
   em `RUNBOOK-FASE-D.md` §5.1–5.3 e `ARMADILHAS.md` §1 H16. Volta quando for
   construir o site de vendas.
3. ✅ **FEITO em 23/08/2026** — Rollback drill executado e cronometrado:
   **76s** do "decidi" ao "voltou", contra os 300s do critério. Não foi por SSH:
   virou `gh workflow run rollback.yml` (RITOS §4, `ci/rollback.py` +
   `.github/workflows/rollback.yml`, PR #91). Runs 32678099024 (volta) e
   32678175555 (desfaz), os dois `success`, com a troca de tag e o `healthy` dos
   três serviços do `checkout` impressos no log — e a mudança medida de FORA,
   pela internet pública. Detalhes e números em `RUNBOOK-FASE-D.md` §6.
4. Evidência: saída crua dos dois runs anexada ao PR de fechamento da etapa.

## Depois do esqueleto: as 12 personas douradas

As 12 personas douradas de teste (definidas pelo mantenedor) entram
como suíte `e2e/personas/` — cada uma percorre o funil com sua combinação de método,
bump e comportamento (Pix pago, Pix abandonado→recuperação, cartão recusado→retry,
double-click, refresh no QR...). Elas são o engordamento do esqueleto, nunca o
substituto dele: primeiro o caminho existe, depois ele aguenta gente.
