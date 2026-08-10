# Constituição da Célula: catalogo
> **Jurisdição:** governa apenas `services/catalogo/`. Herda `CONSTITUICAO.md`. Nenhuma outra lei tem autoridade aqui.
> **STATUS:** ATIVA · **Merge:** auto-merge permitido com CI verde

## Missão
Fonte da verdade de SITES, produtos, ofertas, preços e order bumps/upsells.
Registro canônico do multissítio: as células públicas resolvem Host→Site aqui
(`GET /sites/by-host/{host}`). Não processa dinheiro, não conhece pagamento,
não conhece aluno.

## Fronteiras
- **PERMITIDO ESCREVER:** `services/catalogo/**`
- **SOMENTE LEITURA:** `contracts/catalogo.openapi.yaml` (seu contrato), `contracts/eventos/`
- **PROIBIDO (nem ler):** qualquer outra pasta de `services/`, `infra/`, segredos de outras células

## Comunicação
- **Expõe:** API interna conforme `contracts/catalogo.openapi.yaml` (rede Docker; sem rota pública)
- **Consome:** nada
- **Eventos:** nenhum
- **Auth:** Bearer estático por par consumidor (checkout, funil, quiz e alunos → catalogo)

## Invariantes desta célula
- **INV-P11 (fronteira de site):** ofertas são POR SITE (slug único por site);
  host não cadastrado ⇒ 404 — nunca um site padrão.
- Preço é sempre `amount_cents` inteiro — float de dinheiro é proibido em toda a plataforma.
- Oferta publicada nunca é editada destrutivamente: mudanças de preço criam nova versão (o snapshot do checkout depende disso).

## Definição de Pronto
`make ci` verde local (lint + testes + freeze de contrato) · diff dentro do escopo e do orçamento ·
evidência falsificável se tocar invariante. **Não inclui:** E2E, deploy (o CI faz), tocar outras células.

## Ritos
RITOS.md §1 (worktree + declaração), §2 (catraca verde + parada após 2 falhas), §3 (nunca alterar `contracts/` — rito próprio).
