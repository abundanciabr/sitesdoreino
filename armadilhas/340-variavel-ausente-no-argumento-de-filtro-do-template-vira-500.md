---
schema_version: 2
armadilha: 340
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: a régua é uma linha de código por template (não passar variável opcional como ARGUMENTO de filtro); quem a cobra é o teste do caminho triste de cada tela, que já é obrigatório (fail-closed na borda), e foi ele que achou esta
sinal:
  - `VariableDoesNotExist: Failed lookup for key`
---

# Variável ausente no ARGUMENTO de um filtro de template não é silenciosa: é `VariableDoesNotExist`, e a tela responde 500

**Sintoma.** O caminho triste de uma tela (a porta de máquina caiu no meio de
um POST, e a view devolve o rascunho sem cabeçalho) responde **500** em vez
da página com o texto preservado. O log diz:

```
django.template.base.VariableDoesNotExist: Failed lookup for key [aula] in [...]
```

O caminho feliz da mesma tela, com a mesma variável em `{{ aula.versao }}` e
`{% if aula.publicada %}`, está verde e sempre esteve.

**Causa.** O Django engole variável inexistente em DOIS lugares e em UM não:

| onde a variável aparece | variável ausente vira |
|---|---|
| `{{ aula.numero }}` | texto vazio (`string_if_invalid`), em silêncio |
| `{% if aula.publicada %}` | falso, em silêncio (`ignore_failures=True`) |
| **argumento de filtro:** `{{ x\|default:aula.numero }}` | **`VariableDoesNotExist`, 500** |

`FilterExpression.resolve` resolve os argumentos de cada filtro com
`arg.resolve(context)` sem `try`. Só o objeto principal da expressão tem a
rede de proteção. Dentro de `{% url 'rota' numero|default:aula.numero %}` a
regra é a mesma: o `default` é um filtro, e `aula.numero` é o argumento dele.

Isso aparece justamente nas telas que têm um cabeçalho que ÀS VEZES não vem
(a porta caiu, e a view manda `sem_cabecalho: True` sem `aula`): quem escreve
o template usa `|default:` para "cair" no cabeçalho quando ele existe, e a
expressão explode exatamente no caso em que ela deveria salvar.

**Solução.** A view passa SEMPRE o valor que a rota precisa, num nome próprio,
em todos os ramos (`"numero": numero`), e o template usa a variável direta:
`{% url 'escola_aula_salvar' numero %}`. Um `default` cujo argumento pode não
existir não é padrão de contingência, é o defeito com outro nome. Régua de
uma linha: **argumento de filtro nunca é variável opcional**.

**Como foi achado.** Pelo teste do caminho triste, e só por ele
(`services/admin/tests/test_editor_de_aulas.py::test_salvar_com_a_sala_fora_do_ar_devolve_o_rascunho_e_nao_diz_que_salvou`).
Três telas irmãs desta casa (`/admin/economia/`, `/admin/escola/jornadas/`,
`/admin/livro/`) não caíram nela porque não têm cabeçalho opcional. É a
`RETROSPECTIVA-FASE-D` §1 em miniatura: o caminho feliz verde não mede o
caminho triste, e o caminho triste é o que a pessoa vê no pior dia.

**Origem:** TAR-152, o editor de encomendas do curso (`/admin/escola/aulas/`,
05/09/2026), no ramo "a sala de aula caiu no meio da edição, e o texto não
pode se perder".
