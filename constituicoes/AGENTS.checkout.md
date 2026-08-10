# Constituição da Célula: checkout
> **Jurisdição:** governa apenas `services/checkout/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** SEMPRE humano (CODEOWNERS) — célula adjacente ao dinheiro

## Missão
Sessões de checkout, snapshot imutável do pedido, order bumps e a orquestração da UI de
pagamento. O checkout **não** conhece o Mercado Pago (só a public key p/ montar o Brick);
quem cobra é a célula pagamentos, via API.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/checkout/**`
- **SOMENTE LEITURA:** `contracts/catalogo.openapi.yaml`, `contracts/pagamentos.openapi.yaml`, `contracts/eventos/`
- **PROIBIDO (nem ler):** as demais células, `infra/`, credenciais MP (não existem aqui — INV-P8)

## Comunicação
- **Expõe:** páginas públicas `/checkout/*` + API interna conforme `contracts/checkout.openapi.yaml`
- **Consome:** catalogo (ofertas/preços), pagamentos (intents) — em dev, SEMPRE via mock `prism`
- **Emite:** `pedido.criado.v1` · **Escuta:** `pagamento.aprovado.v1`, `pagamento.recusado.v1`, `pix.expirado.v1` (atualizam o status local do pedido)
- **Banco:** `checkout_db` (role `checkout_user`)

## Doutrina interna — Pix e cartão nunca se tocam
```
templates/checkout/{dados,pix,cartao}.html
static/checkout/{api.js,dados.js,pix.js,cartao.js}
```
`api.js` é um cliente fetch fino. Cada página é uma ilha Alpine autossuficiente —
**zero estado compartilhado entre dados/pix/cartão**; comunicação só via servidor e snapshot.
`pix.js` não contém uma linha sobre cartão; `cartao.js` (Card Payment Brick) não contém
uma linha sobre Pix, e a página do Pix nem carrega o SDK do MP.

## Invariantes desta célula (guardas em INVARIANTES.md)
- **INV-P11 (multissítio):** o site NUNCA vem do payload — é resolvido do Host
  (CONV-SITE); host desconhecido = 404; snapshot e `pedido.criado.v1` carregam
  `site_id`; sessão do site A não fecha pedido com oferta do site B.
- **INV-P1** Snapshot do pedido é create-only. · **INV-P2** Cliente envia intenção
  (`bump_ids`), servidor calcula dinheiro do catálogo. · **INV-P7** UI de status deriva
  do servidor, nunca do passo do wizard.
- Mobile-first por contrato: teste-guarda `checkout/tests/test_mobile_first_contract.py`.
- UTM/atribuição do funil chega intacta ao `pedido.criado.v1` (Meta CAPI).

## Definição de Pronto
`make ci` verde · freeze de contrato verde · evidência falsificável para qualquer toque
em invariante · diff no escopo/orçamento. **Não inclui:** E2E, deploy, tocar pagamentos.

## Ritos
RITOS.md §1, §2. Mudança no contrato próprio ou no de pagamentos = rito §3 com o mantenedor.
