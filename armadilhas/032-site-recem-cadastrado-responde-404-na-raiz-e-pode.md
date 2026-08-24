<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.13  ·  referencias antigas "ARMADILHAS §4.13" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.13 Site recém-cadastrado responde 404 na raiz — e pode SEGUIR 404 por 60s depois do cadastro

**Sintoma:** o site novo está cadastrado no catálogo (o `Site` existe, `active=True`),
o DNS aponta certo, e `https://<dominio>/` responde **404**. Cadastrou de novo, "já
existia", e o 404 continua — por até um minuto.
**Causa dupla:**
1. O comando `criar_site` (Receita R11) **não preenche `default_offer_slug`**, e a
   landing do funil levanta `Http404("site sem oferta padrão configurada")` para site
   sem oferta padrão (`services/funil/apps/core/views.py`). Site cadastrado ≠ site
   servindo: sem oferta, a raiz é 404 por construção.
2. O CONV-SITE do funil cacheia a resolução host→site por **60s, inclusive o 404**
   (`services/funil/apps/core/middleware.py`, `TTL_SEGUNDOS`). Qualquer requisição que
   chegou ANTES do cadastro (um bot, o próprio smoke rodado cedo demais) deixa o 404
   cacheado — o cadastro certo continua parecendo errado até o TTL vencer.
**Solução:** cadastro de site vai por `infra/sites.json` (deploy-infra, passo 5 — a
R11 mecanizada): o formato **exige** `default_offer_slug` apontando para uma das
ofertas do arquivo, o sync cria site+produto+oferta juntos, e o smoke do run insiste
por ~80s justamente para atravessar o TTL do cache — 404 depois disso é reprovação
real. Se algum dia for cadastrar à mão, crie as três coisas juntas e espere o TTL
antes de concluir qualquer coisa a partir de um 404.
**Origem:** sessão meshcraft.top (23/08/2026), ao mecanizar a R11.
