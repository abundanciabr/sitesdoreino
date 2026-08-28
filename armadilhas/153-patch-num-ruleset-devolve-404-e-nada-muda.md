# `PATCH` num ruleset do GitHub devolve 404 e **nada muda** — a leitura seguinte é a única testemunha

**Sintoma:** você muda uma regra de proteção da `main` pela API e o comando
"passa" sem estardalhaço. A conferência seguinte mostra o valor **antigo**:

```bash
gh api --method PATCH repos/<dono>/<repo>/rulesets/<id> --input regras.json
# → {"message":"Not Found","status":"404"}

gh api repos/<dono>/<repo>/rulesets/<id> --jq '...strict_required_status_checks_policy'
# → false      ⟵ continua como estava. Nada foi alterado.
```

O que torna isto perigoso não é o 404 — é o **contraste**: o `GET` do mesmo
caminho funciona, e outras operações de administração do mesmo token funcionam
(`PATCH` no próprio repositório liga rastreamento de segredos sem reclamar).
Então a leitura natural do 404 é "meu corpo JSON está errado" ou "não tenho
permissão", e as duas estão erradas.

**Causa:** o endpoint de rulesets do repositório **não aceita `PATCH` por este
caminho** — ele responde `404`, não `405`, o que apaga a pista. A atualização
funciona com **`PUT`, e com o objeto COMPLETO** (`name`, `target`,
`enforcement`, `conditions`, `bypass_actors`, `rules` inteiro). Mandar só o
campo que você quer mudar não serve: o `PUT` substitui o objeto, e o que faltar
some.

**Solução:**

```bash
# 1. leia o objeto inteiro e guarde
gh api repos/<dono>/<repo>/rulesets/<id> > /tmp/ruleset.json

# 2. edite SÓ o campo desejado, preservando todo o resto
#    (name, target, enforcement, conditions, bypass_actors, rules)

# 3. PUT com o objeto completo
gh api --method PUT repos/<dono>/<repo>/rulesets/<id> --input /tmp/ruleset.json

# 4. PROVA DE FORA — releia e compare os campos que NÃO deviam mudar
gh api repos/<dono>/<repo>/rulesets/<id> \
  --jq '{enforcement, bypass:(.bypass_actors|length), tipos:[.rules[].type]}'
```

O passo 4 não é zelo: sem ele o passo 1 desta armadilha não teria sido
descoberto. **Comando de configuração que não é relido não foi executado — foi
torcido.** É a categoria *prova de fora* da `RETROSPECTIVA-FASE-D`, aplicada a
um lugar onde ninguém espera precisar dela, porque não há teste nem CI cobrindo
configuração de plataforma.

**Duas notas que economizam rodada:**

- `require_extra_approval_for_unattributed_changes` e `required_reviewers`
  aparecem no `GET` mas **não precisam ir no `PUT`** — o GitHub os repõe. Não
  monte o corpo à mão a partir da documentação; parta sempre do `GET`.
- Se o `PUT` também devolver 404, aí sim é permissão: o token precisa de
  administração do repositório. `gh auth status` mostra os escopos; escopo
  `repo` costuma bastar em repositório próprio.

**Origem:** Onda 0 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`, em
28/08/2026 — ao ligar `strict_required_status_checks_policy` (a trava da colisão
semântica, Classe 6). O `PATCH` respondeu 404 duas vezes, inclusive com um corpo
mínimo de um campo só; o `PUT` com o objeto completo funcionou na primeira.
**Categoria** (`RETROSPECTIVA-FASE-D`): prova de fora · falso-verde.
