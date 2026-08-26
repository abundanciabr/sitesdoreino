# Ligar a proteção nativa da `main` e travar TODO merge para sempre — `Review required` num repositório de um colaborador só

**Sintoma:** logo depois de criar a branch protection (ruleset ou clássica) na
`main`, **nenhum PR mergeia mais** — nem os verdes. O GitHub diz `Review
required`, ou `Waiting for status to be reported` num check que nunca chega, e
não há segunda pessoa no repositório para aprovar. O repositório fica lacrado
com a chave do lado de dentro.

**Causa:** três armadilhas independentes, todas do mesmo formato "ligou o que
parecia óbvio":

1. **`required_approving_review_count` maior que 0.** O GitHub **proíbe aprovar
   o próprio PR**, e aqui só existe UM colaborador (§1, H9). Exigir 1 aprovação
   = exigir uma pessoa que não existe. O mesmo vale, com dobro de força, para
   `require_code_owner_review`: o `CODEOWNERS` da raiz aponta `@abundanciabr`
   em `contracts/`, `ci/`, `.github/`, `infra/` e nos arquivos-lei — ligar isso
   travaria PARA SEMPRE exatamente os caminhos mais críticos.
2. **Exigir um check que nem sempre roda.** Em todo PR daqui aparecem quatro
   check-runs: `detectar`, `muralhas`, `ci-celula` e `ci-celula-gate`. O
   `ci-celula` fica **`skipped`** quando o PR não toca célula nenhuma (a maioria
   dos PRs de documentação e de painel) — e um required check `skipped` conta
   como satisfeito, que é o falso-verde do [INV-CI01] entrando pela porta da
   frente. O check terminal que SEMPRE roda (`if: always()`) e que consolida a
   tabela-verdade é o **`ci-celula-gate`**. Exija `muralhas` e `ci-celula-gate`;
   nunca `ci-celula`, nunca `detectar`.
3. **`require_extra_approval_for_unattributed_changes`, que o GitHub liga
   sozinho.** Não se pede esse campo: ele vem `true` por padrão na resposta do
   POST. Ele exige uma aprovação EXTRA quando algum commit do PR não está
   atribuído a uma conta do GitHub (e-mail de autor não cadastrado) — o que,
   num repositório de um colaborador só, é o mesmo deadlock do item 1. Hoje
   todos os commits daqui são atribuídos (`author.login = abundanciabr`), então
   ele dorme; se um dia um PR travar pedindo aprovação sem motivo aparente,
   **é ele** — confira com `gh api repos/<owner>/<repo>/commits/<sha> --jq
   '.author.login'` e desligue o parâmetro no ruleset.

**Solução:** a configuração que ficou de pé em 26/08/2026 (ruleset "main
protegida", id 21570247), e o porquê de cada peça:

```jsonc
"rules": [
  { "type": "deletion" },          // ninguém apaga a main
  { "type": "non_fast_forward" },  // ninguém reescreve a história da main
  { "type": "pull_request", "parameters": {
      "required_approving_review_count": 0,   // NÃO aumente: não há 2º humano
      "require_code_owner_review": false,     // idem, e travaria ci/ e .github/
      "allowed_merge_methods": ["merge","squash","rebase"] } },
  { "type": "required_status_checks", "parameters": {
      "strict_required_status_checks_policy": false,  // ver abaixo
      "required_status_checks": [
        { "context": "muralhas",       "integration_id": 15368 },
        { "context": "ci-celula-gate", "integration_id": 15368 } ] } }
]
```

`required_approving_review_count: 0` **não** enfraquece nada aqui: o que segura
é o `required_status_checks`, e a revisão humana prévia saiu do fluxo por
decisão de 22/08/2026 (`docs/decisoes/DECISAO-merge-pelo-agente.md`).
O `integration_id: 15368` é o app do GitHub Actions — sem ele, qualquer
integração que reportasse um status chamado `muralhas` satisfaria o portão.

`strict_required_status_checks_policy: false` é deliberado: `true` exige que a
branch esteja atualizada com a `main` no instante do merge, e num lote de PRs
paralelos (`RUNBOOK-LOTES.md`) cada merge invalidaria todos os outros, forçando
rebase + CI inteira de novo, um por um, em série. O ganho (pegar conflito
semântico) não paga esse preço enquanto os PRs forem pequenos e de células
diferentes.

**`bypass_actors` vazio, de propósito** — `current_user_can_bypass: "never"`,
inclusive para o dono e para o agente (que usa o token dele). Rulesets, ao
contrário da branch protection clássica, **não isentam administrador por
padrão**; foi por isso que o ruleset foi escolhido em vez da regra clássica.
A porta de emergência não é um bypass silencioso: é desligar o ruleset, que é
um ato visível e auditável —
`gh api -X PUT repos/<owner>/<repo>/rulesets/21570247 -f enforcement=disabled`.

**Como PROVAR que ligou (prova de fora, não print de tela):** tente escrever na
`main` pela API, que ignora o `.githooks/pre-push` local:

```bash
gh api -X PUT repos/<owner>/<repo>/contents/docs/prova.txt -f message=teste \
  -f content="$(printf 'x' | base64)" -f branch=main
```

Resposta esperada: **HTTP 409** `Repository rule violations found / Changes must
be made through a pull request. / 2 of 2 required status checks are expected.`
Se vier 201, a trava não está valendo. `gh api repos/<owner>/<repo>/rules/branches/main`
lista as regras que o GitHub considera ativas — é a fonte, não a tela de settings.

**Origem:** 26/08/2026, ao fechar o H3 (`ARMADILHAS-OPERACAO.md` §1) — a
pendência mais velha do livro do painel, aberta em 19/08/2026 quando a proteção
nativa era paga e destravada em 23/08/2026 quando o repositório virou público.
