# Constituição da Célula: funil
> **Jurisdição:** governa apenas `services/funil/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde

## Missão
Landing pages, páginas de vendas, captura. A vitrine. Sem banco próprio: formulários
postam na API de leads; botão de compra redireciona para `/checkout/<oferta>`.
A IA pode reescrever a vitrine 100 vezes sem encostar em dinheiro.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/funil/**`
- **SOMENTE LEITURA:** `contracts/catalogo.openapi.yaml`, `contracts/leads.openapi.yaml`
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de pagamento

## Comunicação
- **Expõe:** páginas públicas (rota `/` no gateway)
- **Consome:** catalogo (dados de oferta, server-side) e leads (POST de
  captura) — via mock `prism` em dev. Também identidade (`GET /interno/sessao`,
  `getSession`) para reconhecer o visitante, e notificacoes (`GET /resumo`,
  `obterResumo`) para o contador do sino — as duas fail-open por desenho: fora
  do ar, a página abre normal sem sessão/sem sino, nunca cai
  (`DECISAO-onde-mora-a-sessao.md`, `DECISAO-fase-4-do-sininho.md`)
- **Auth:** Bearer dedicado (`TOKEN_CATALOGO`, `TOKEN_LEADS`,
  `IDENTIDADE_API_TOKEN`, `NOTIFICACOES_API_TOKEN`)

## Invariantes desta célula
- **Multissítio (INV-P11):** o site vem do Host (middleware CONV-SITE, cache 60s);
  host não cadastrado = 404. A landing renderiza da configuração do site — nunca
  hardcode de marca.
- **Mobile-first por contrato**: templates críticos estendem `base_mobile.html`; teste-guarda `funil/tests/test_mobile_first_contract.py` trava o layout. Nunca afrouxar.
- UTM/atribuição preservada em toda navegação para o checkout (querystring intacta — Meta CAPI depende disso).

## Definição de Pronto
`make ci` verde · Lighthouse mobile ≥ 90 nas páginas críticas (meta, não portão) · diff no escopo.

## Ritos
RITOS.md §1, §2. Zero acesso a `contracts/` para escrita.
