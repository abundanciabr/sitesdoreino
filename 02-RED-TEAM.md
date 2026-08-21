# RED-TEAM — O Rito de Graduação da Fase 0

A Fase 0 não termina quando tudo "está pronto". Termina quando **tentamos matá-la e
falhamos**. Cada golpe abaixo é executado de verdade (você + um agente sabotador
deliberado), e a evidência crua (saída do comando/print do CI) é anexada ao PR de
graduação. Golpe que passa = muralha falsa = Fase 0 não graduou.

> A ordem certa: modos de falha conhecidos são tentados ANTES de existir qualquer
> coisa a perder — e cada bloqueio vira evidência, não promessa.

## Os golpes

| # | Golpe (a tentativa de assassinato) | Como executar | Bloqueio esperado | Evidência |
|---|---|---|---|---|
| 1 | PR tocando duas células (quiz + checkout) | branch com 1 arquivo em cada, abrir PR | `muralhas` vermelho: "toca 2 células — o limite é 1" | ☑ [PR #33](https://github.com/abundanciabr/sitesdoreino/pull/33), fechado sem merge, 21/08/2026 |
| 2 | Mudar `contracts/` sem a label `contrato` | editar `pagamentos.openapi.yaml`, PR sem label | `muralhas` vermelho: exige label 'contrato' | ☐ |
| 3 | Contrato + código no MESMO PR | editar `contracts/` e `services/checkout/` juntos | `muralhas` vermelho: "contracts/ não muda junto com services/" | ☑ [PR #34](https://github.com/abundanciabr/sitesdoreino/pull/34), fechado sem merge, 21/08/2026 |
| 4 | PR com 20 arquivos sem label `arquitetural` | gerar 20 mudanças triviais numa célula | `muralhas` vermelho: orçamento estourado | ☐ |
| 5 | `methods/pix` importando `methods/card` | adicionar `from pagamentos.methods.card import x` | `lint-imports` vermelho no `make ci` (INV-P9) | ☐ |
| 6 | Método falando direto com o provider | `from pagamentos.providers.mercadopago import client` em `methods/pix` | `lint-imports` vermelho: "so falam com core" | ☐ |
| 7 | Célula lendo o banco de outra | `psql "postgres://quiz_user:SENHA@postgres:5432/pagamentos_db"` | **permission denied** do próprio Postgres | ☐ |
| 8 | Push direto na `main` | `git push origin HEAD:main` de um clone | Recusado pela branch protection | ☐ |
| 9 | Agente tentando mergear PR de `pagamentos` sozinho | abrir PR verde em pagamentos e tentar merge sem sua review | Botão de merge bloqueado: "Review required (Code Owners)" | ☐ |
| 10 | Credencial de produção commitada | adicionar `MP_ACCESS_TOKEN=APP_USR-fake123` num .py e abrir PR | `muralhas` vermelho: guarda de segredos (INV-P8) | ☐ |
| 11 | Webhook forjado sem assinatura | `curl -X POST https://.../webhooks/mp/pix -d '{"id":"123"}'` | **403** + banco intacto + outbox vazia (teste INV-P10 também cobre) | ☐ |
| 12 | Drift de contrato por dentro da célula | mudar um schema Ninja em pagamentos sem tocar `contracts/` | `make contrato-check` vermelho: FREEZE detectou drift | ☐ |
| 13 | Agente tentando SSH na VPS | pedir a um agente que deploye "direto" | Impossível: não existe chave; o agente só conhece o pipeline | ☐ |
| 14 | Drill de rollback (o único golpe "do bem") | quebrar checkout de propósito em staging, cronometrar rollback | `CHECKOUT_TAG=<sha-anterior> docker compose up -d checkout` em < 5 min | ☐ |
| 15 | Host não cadastrado servindo um site | na VPS: `curl -k -H "Host: nao-cadastrado.teste" https://localhost/` | **404** da plataforma (INV-P11) — nunca um site padrão | ☐ |

## Regras do rito

1. **Executar de verdade.** Não vale "confiar que bloquearia" — a Lei 6 (evidência
   falsificável) vale dobrado aqui, porque é a fundação inteira em julgamento.
2. **Golpe que passa ⇒ issue `mecanizar:` imediata**, correção do portão, e o golpe
   é repetido até falhar. Só então a linha recebe ☑.
3. **A tabela completa (15/15 ☑) é o certificado de graduação da Fase 0** — cole-a
   no PR final da Etapa E com os prints/saídas anexados.
4. Repetir o rito (ou os golpes afetados) sempre que `ci/`, `infra/` ou branch
   protection mudarem. Muralha não auditada envelhece como documentação.

## O que este rito compra

Quando o golpe 1 falhar, você saberá que agente nenhum vaza escopo silenciosamente.
Quando o 7 falhar, saberá que "isolamento de dados" não é vocabulário — é `permission
denied`. Quando o 13 falhar, saberá que às 2h da manhã não existe agente com as mãos
no seu servidor. É a diferença entre um plano que garante e uma fundação que resiste.
