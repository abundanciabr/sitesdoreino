<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §5 — Portões mecânicos do CI (eles reprovam de verdade)
     ID historico: §5.3  ·  referencias antigas "ARMADILHAS §5.3" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 5.3 CI vermelho por variável de ambiente que existe só na sua máquina

**Sintoma:** `make ci` verde local, `ImproperlyConfigured: variável obrigatória
ausente: X` no CI.
**Causa:** toda variável **nova e fail-hard** (`env()`, convenção CONV v1) declarada
em `config/settings.py` precisa ser espelhada no bloco `env:` do job **`rodar`** em
`.github/workflows/ci-celula.yml` — é o único lugar que fornece env vars para o
`make ci` do CI real. Seu `.env.dev` local (gitignored) sobrevive entre sessões e
**mascara** o esquecimento.
**Solução:** ao adicionar `env("NOVA")`, abra o workflow no mesmo PR. Ou, quando fizer
sentido, **evite o problema**: leia a variável no ponto de uso (`os.environ[...]`
dentro do cliente/middleware, como fazem as receitas R2 e CONV-SITE) em vez de no
`settings.py` — aí nada é fail-hard no import e o CI não precisa conhecê-la.
**Origem:** Prompt 3a (pagamentos, PR #16).
