# Script injetado no container que já roda importa símbolo NOVO — e trava o canal de deploy inteiro

**Sintoma:** o merge de um PR de célula deixa os DOIS deploys vermelhos de uma vez.

```
deploy-infra  ImportError: cannot import name 'normalizar_idiomas' from 'apps.sites.models'
deploy-celula portao-de-deploy: vermelhos-nao-previstos: .github/workflows/deploy-infra.yml => failure
```

Produção continua 100% saudável (nada subiu — o portão é fail-closed e fez o
certo). O que quebrou não foi o site: foi o **canal** de entrega, e ele fica
travado até alguém consertar o script, porque as duas correções óbvias se
mordem (ver o impasse abaixo).

**Causa: o script viaja, a imagem não.** O `deploy-infra` injeta
`infra/sincronizar_sites.py` DENTRO do container do catálogo que já está de pé
na VPS:

```yaml
docker compose exec -T -e SITES_JSON="$(cat sites.json)" \
  catalogo python manage.py shell -c "$(cat sincronizar_sites.py)"
```

O arquivo é do commit RECÉM-mergeado; o container roda a imagem ANTERIOR. Um
`from apps.sites.models import Site, normalizar_idiomas` no topo do script pede
à imagem velha um símbolo que só nasceu na imagem nova. `ImportError` na linha
de import — antes de qualquer linha útil rodar.

**O impasse, que é a parte cara** (é ele que transforma um erro de uma linha
num canal travado):

- a imagem nova só chega à VPS pelo **`deploy-celula`**;
- o `deploy-celula` só passa se o **`deploy-infra`** estiver verde (o
  `portao-de-deploy` reprova com `vermelhos-nao-previstos` quando um workflow
  irmão do mesmo SHA falhou — e está certíssimo em reprovar);
- o `deploy-infra` só fica verde **com a imagem nova**.

E não há como "só mergear na ordem certa": os dois workflows disparam **em
paralelo** no mesmo `push` para a `main`, sem ordem entre eles. Mexer no
workflow para serializar seria pagar com acoplamento permanente um problema que
é do script.

**Solução — o script é que tem de ser tolerante à idade da imagem.** Duas
regras, e a segunda é a que costuma faltar:

1. **Zero import de símbolo recém-criado da célula.** Só o que existe em toda
   imagem: os modelos do ORM (`Site`, `Product`, `Offer`) e `django.db`.
   Precisa da regra que mora no modelo? **Copie-a** para o script.
2. **Campo que a imagem/banco em execução ainda não conhece vira pendência
   DECLARADA, nunca exceção.** Detecte pelo Django e siga em frente:

```python
def idioma_disponivel():
    no_modelo = {campo.name for campo in Site._meta.get_fields()}
    if [n for n in CAMPOS_DE_IDIOMA if n not in no_modelo]:
        return False, "a imagem em execução não tem os campos ..."   # TOLERA
    with connection.cursor() as cursor:   # ANTES do atomic() (§4.8)
        no_banco = {c.name for c in connection.introspection
                    .get_table_description(cursor, Site._meta.db_table)}
    if [n for n in CAMPOS_DE_IDIOMA if Site._meta.get_field(n).column
            not in no_banco]:
        raise SystemExit("ERRO: ... o `migrate` NÃO rodou ...")       # REPROVA
    return True, ""
```

Sincroniza tudo o que consegue, imprime um aviso inequívoco (motivo, campos
NOMEADOS, sites afetados, por que o run segue verde, e que re-rodar o
`deploy-infra` depois do `deploy-celula` fecha a pendência) e **sai com
sucesso**. Nunca grave torto e nunca finja que gravou.

**Três detalhes que fazem diferença:**

- **A tolerância vale para a IMAGEM, não para o BANCO** — e essa assimetria é
  medida, não preguiça. Modelo com os campos + tabela sem as colunas (`migrate`
  não rodou) **não** admite "sincronizar o que dá": todo `SELECT` do Django pede
  TODAS as colunas do modelo, então nem `Site.objects.get_or_create(host=...)`
  roda — `OperationalError: no such column: sites_site.default_language`. Ali o
  certo é reprovar com mensagem de operador; um aviso amarelo seguido de exit 0
  seria fingir. (E esse estado não é ordem de workflow: é célula
  meio-implantada, com o catálogo já devolvendo erro para quem o consome.)
  A sonda roda ANTES do `transaction.atomic()` nos dois casos — erro de banco
  capturado dentro da transação envenena a transação inteira (§4.8).
- **A validação fail-closed NÃO pode ser afrouxada junto.** Declaração
  incoerente no `sites.json` continua reprovando o deploy em qualquer idade de
  imagem: arquivo torto é erro do Git, e escondê-lo atrás da tolerância seria
  fingir que passou.
- **Cópia consciente exige guarda mecânica** (RESOLVIDAS.md §5.11). A regra
  copiada do modelo derivaria em silêncio; o guarda roda as duas implementações
  lado a lado sobre um corpo de casos, exige a mesma decisão e a mesma
  mensagem, e um terceiro teste confere que o corpo de casos dispara **todos**
  os `raise` dos dois lados — regra nova de um lado só fica vermelha nomeando a
  linha que ninguém exercita. Ver `ci/tests/test_sincronizar_sites_tolerante.py`.

**Como testar "a imagem velha" sem ter uma imagem velha:** a suíte da célula não
serve — o modelo real é sempre a versão nova, e não há como pedir a ele que
finja não ter o campo. Monte um Django de mentira em `sys.modules`
(`django.db`, `django.core.exceptions`, `apps.*.models`) e `exec()` o script cru
com `SITES_JSON` no ambiente; o `Site` falso tem os campos ou não, conforme a
idade que você quer simular. Com o arnês fiel, a evidência vermelha reproduz o
erro de produção **palavra por palavra** — inclusive a linha do import.

**E depois confira o arnês contra o Django DE VERDADE** — foi assim que a
assimetria do detalhe acima apareceu: as 22 provas contra o Django falso estavam
**verdes** para o caso "banco não migrado", e o mesmo caso contra Django+SQLite
reais estourou `OperationalError` na primeira query. O ORM falso respondia à
pergunta que o teste fazia; o real também impõe as colunas que ninguém pediu.
Dois modos baratos de fazer essa conferência, sem Docker e sem tocar em
`services/`:

```bash
# a) o estado "migrate não rodou": modelo em 0002, tabela em 0001
DATABASE_URL="sqlite:///$SCRATCH/e2e.sqlite3" python manage.py migrate sites 0001
DATABASE_URL=... SITES_JSON="$(cat ../../infra/sites.json)" \
  python manage.py shell -c "$(cat ../../infra/sincronizar_sites.py)"

# b) a IMAGEM VELHA inteira, materializada do próprio histórico
git archive <commit-antes-da-fase> services/catalogo | tar -x -C "$SCRATCH/velha"
```

O (b) é a prova que vale: `manage.py shell -c` de verdade, modelo antigo de
verdade, e a sequência completa do destravamento medida num só banco — imagem
velha converge e declara a pendência (exit 0) → `migrate` → re-run grava
`ajustado: site <host> (default_language, languages)`.

**Vale para qualquer script injetado, não só para este.** A pergunta a fazer
antes de acrescentar um import a um arquivo que roda dentro de um artefato
versionado à parte é sempre a mesma: *este símbolo existe na versão que já está
lá?* Se a resposta depender da ordem de dois pipelines, a resposta é não.

**Origem:** merge do PR #106 (`93e673c`, fase 4 do i18n), 24/08/2026 — runs
32713472883 (`deploy-infra`, causa raiz) e 32713472907 (`deploy-celula`,
vítima). Corrigido no despacho infra/sync-tolerante, no mesmo dia.
