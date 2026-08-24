<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.7  ·  referencias antigas "ARMADILHAS §4.7" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.7 Cache de módulo vaza entre testes

**Sintoma:** teste passa sozinho e falha na suíte (ou o contrário), envolvendo
resolução de site/host.
**Causa:** o cache do CONV-SITE é um `dict` de nível de módulo — sobrevive entre
testes, inclusive cacheando o 404.
**Solução:** exponha uma função de limpeza (`limpar_cache_de_sites()`) e chame numa
fixture `autouse` antes e depois de cada teste.
**Origem:** Prompt 4 (checkout).
