---
schema_version: 2
armadilha: 210
estado: guardada
degrau: 4
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/funil/apps/i18n/validador.py
sinal:
  - `\[i18n\] catálogo inválido — célula não sobe`
  - `obsoleta — .?_fonte.? ≠ hash\(en\)`
---

# Editar o texto `en` de uma tradução derruba a célula `funil` inteira: o `_fonte` virou carimbo velho

**Sintoma:** você corrige uma frase em `services/funil/traducoes/*.yaml` — um
typo, uma vírgula, a troca de um travessão — e o `ci-celula (funil)` reprova sem
que teste nenhum tenha falhado. A célula nem sobe:

```
django.core.exceptions.ImproperlyConfigured: [i18n] catálogo inválido — célula não sobe (D4 fail-closed):
  - login.titulo: obsoleta — `_fonte` ≠ hash(en) (esperado d241b2); traduza e recalcule, ou declare `pendente`
```

**Causa:** cada chave do catálogo carrega `_fonte`, que é `sha256(valor_en)[:6]`
tirado **no momento da tradução** (PLANO-I18N, decisão D4). Ele existe para uma
pergunta só: *a tradução ainda corresponde à fonte, ou o inglês andou e o
português ficou para trás?* Mexer no `en` sem recalcular é literalmente o
estado que ele foi construído para detectar. O portão não está confuso — ele
está certo, e o `ready()` do app derruba a célula de propósito (fail-closed):
publicar tradução que não corresponde à fonte é pior que não subir.

**Solução — três caminhos legítimos, e nenhum deles é "apagar o `_fonte`":**

1. **Traduziu junto** (o caso normal ao editar copy): recalcule o hash de cada
   chave tocada. A própria mensagem do CI já entrega o valor esperado, chave por
   chave — `esperado d241b2` é o que vai entre aspas.
2. **Ainda não traduziu:** ponha `_fonte: "pendente"`. É honesto e o portão
   aceita, menos em texto jurídico.
3. **Mudou o `en` sem mudar o sentido** (um espaço, uma vírgula): recalcule e
   marque a linha com `# revisado-sem-alteracao`. É o caso auditável e
   greppável que a regra anti-burla previu.

**A segunda metade da armadilha, que pega quem só recalcula:** a regra
**anti-burla** compara o diff contra `origin/main` e exige que, se o `_fonte`
mudou, os idiomas não-base tenham mudado **também**. Recalcular o hash e deixar
`pt-br`/`es` intactos reprova de novo, agora com outra mensagem. Isso é de
propósito: sem ela, recarimbar seria mais barato que traduzir (é a mesma doença
da `armadilhas/050`).

**Como recalcular sem errar a conta:** o hash é do valor `en` cru, e para chave
com plural é a forma canônica (`"\n".join(f"{k}={v[k]}" for k in sorted(v))`) —
está em `services/funil/apps/i18n/catalogo.py::hash_da_fonte`. Associe hash e
linha pela **ordem do documento**, que é a mesma regra que o validador usa
(`dict(zip(planas, linhas_fonte))` em `_comparar_fontes`); reescreva só o hash
entre aspas, para o comentário da linha sobreviver.

**Contexto:** caiu em 30/08/2026 no PR #600, ao trocar os travessões do texto
publicado (`CLAUDE.md`, "Nenhum texto publicado sai com travessão"). Dez chaves
de uma vez, nos três idiomas. O conserto foi um script de 40 linhas; achar o
motivo foi o caro, porque a reprovação chega como "a célula não sobe" e não como
"um teste falhou".
